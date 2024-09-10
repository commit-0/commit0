import argparse
import docker
from enum import StrEnum, auto
import os
import traceback
import yaml
from pathlib import Path
import logging

from commit0.harness.constants import RUN_PYTEST_LOG_DIR
from commit0.harness.docker_build import (
    close_logger,
    setup_logger,
)
from commit0.harness.docker_utils import (
    cleanup_container,
    create_container,
    copy_from_container,
    copy_to_container,
    copy_ssh_pubkey_from_container,
    delete_file_from_container,
    exec_run_with_timeout,
)
from commit0.harness.spec import Spec, make_spec
from commit0.harness.utils import (
    EvaluationError,
    extract_test_output,
    get_hash_string,
    get_ip,
    get_user,
)


class ExecutionBackend(StrEnum):
    DOCKER = auto()
    MODAL = auto()


def run_docker(
    spec: Spec, logger: logging.Logger, eval_file: Path, timeout: int, log_dir: Path
) -> None:
    client = docker.from_env()
    container = None
    try:
        container = create_container(
            client=client,
            image_name=spec.repo_image_key,
            container_name=spec.get_container_name(),
            logger=logger,
        )
        container.start()
        copy_ssh_pubkey_from_container(container)

        logger.info(f"Eval script written to {eval_file}; copying to container...")
        copy_to_container(container, eval_file, Path("/eval.sh"))

        # Run eval script, write output to logs
        output, timed_out, total_runtime = exec_run_with_timeout(
            container, "/bin/bash /eval.sh", timeout
        )
        logger.info(output)

        test_output = extract_test_output(
            output, "--json-report --json-report-file=report.json"
        )
        # stdout might be more straightforward
        print(test_output)
        test_output_path = log_dir / "test_output.txt"
        with open(test_output_path, "w") as f:
            f.write(test_output)
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    spec.repo,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )

        # copy back report.json if there is any
        report_file = Path(spec.repo_directory) / "report.json"
        # Run the test command inside the container to check if the file exists
        exit_code, output = container.exec_run(f"test -e {report_file}", demux=True)
        # Check the exit code of the command
        if exit_code == 0:
            copy_from_container(container, report_file, Path(log_dir / "report.json"))
            delete_file_from_container(container, report_file)

    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (
            f"Error in running pytest for {spec.repo}: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({logger.log_file}) for more information."
        )
        logger.error(error_msg)
    finally:
        # Remove repo container + image, close logger
        cleanup_container(client, container, logger)
        close_logger(logger)


def run_modal(
    spec: Spec, logger: logging.Logger, eval_file: Path, timeout: int, log_dir: Path
) -> None:
    # get image name to pull from dockerhub
    # spec.repo_image_key
    import modal

    reponame = spec.repo.split("/")[-1]
    image_name = f"wentingzhao/{reponame}"
    image = modal.Image.from_registry(image_name)

    with modal.NetworkFileSystem.ephemeral() as nfs:
        # create sleepy sandbox
        sandbox = modal.Sandbox.create(
            "sleep",
            "infinity",
            image=image,
            network_file_systems={
                "/vol": nfs,
            },
        )

        # get ssh pubkey
        process = sandbox.exec("bash", "-c", "cat /root/.ssh/id_rsa.pub")
        public_key = "".join([line for line in process.stdout]).strip()

        # add to authorized keys locally. copy-pasted from utils
        local_authorized_keys_path = os.path.expanduser("~/.ssh/authorized_keys")
        os.makedirs(os.path.dirname(local_authorized_keys_path), exist_ok=True)
        if not os.path.exists(local_authorized_keys_path):
            # Since the file does not exist, create it
            open(local_authorized_keys_path, "a").close()
            write = True
        else:
            with open(local_authorized_keys_path, "r") as authorized_keys_file:
                content = authorized_keys_file.read()
                if public_key not in content:
                    write = True
                else:
                    write = False
        if write:
            with open(local_authorized_keys_path, "a") as authorized_keys_file:
                authorized_keys_file.write(public_key + "\n")

        # copy eval file
        with open(eval_file, "rb") as f:
            nfs.write_file("eval.sh", f)
        sandbox.exec("bash", "-c", "cp /vol/eval.sh /eval.sh")

        # DBG: check if eval file properly copied
        process = sandbox.exec("bash", "-c", "ls /")
        for line in process.stdout:
            print(line)
        # /DBG

        # execute tests
        process = sandbox.exec("bash", "-c", "/bin/bash /eval.sh")
        output = []
        for line in process.stdout:
            output.append(line)
        output = "".join(line)
        logger.info(output)
        print(output)

        output = []
        for line in process.stderr:
            output.append(line)
        output_s = "".join(line)
        logger.info(output_s)
        print(output_s)

        timed_out = False
        total_runtime = 1

        test_output = extract_test_output(
            output_s, "--json-report --json-report-file=report.json"
        )

        # stdout might be more straightforward
        print(test_output)
        test_output_path = log_dir / "test_output.txt"
        with open(test_output_path, "w") as f:
            f.write(test_output)
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    spec.repo,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )


def main(
    repo: str,
    test_ids_ls: list[str],
    timeout: int,
    branch_name: str,
    backend: ExecutionBackend,
) -> None:
    with open("config.yml", "r") as file:
        data = yaml.safe_load(file)
    spec = make_spec(data["repos"][repo])
    test_ids = " ".join(test_ids_ls)
    hashed_test_ids = get_hash_string(test_ids)

    # set up logging
    log_dir = RUN_PYTEST_LOG_DIR / repo / hashed_test_ids
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run_pytest.log"
    logger = setup_logger(repo, log_file)

    # make eval file
    eval_script = spec.eval_script.format(
        local_repo=f"{data['base_repo_dir']}/{repo}",
        branch_name=branch_name,
        test_ids=test_ids,
        ip=get_ip(data["backend"]),
        user=get_user(),
    )
    eval_file = Path(log_dir / "eval.sh")
    eval_file.write_text(eval_script)

    if ExecutionBackend(backend) == ExecutionBackend.DOCKER:
        run_docker(spec, logger, eval_file, timeout, log_dir)
    elif ExecutionBackend(backend) == ExecutionBackend.MODAL:
        run_modal(spec, logger, eval_file, timeout, log_dir)


def add_init_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=str, help="which repo to run unit tests")
    parser.add_argument(
        "--test_ids", type=str, nargs="+", help="which test ids / files / directories"
    )
    parser.add_argument(
        "--branch_name", type=str, help="which git branch to run unit tests"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1_800,
        help="Timeout (in seconds) for running tests for each instance",
    )
    parser.add_argument(
        "--backend",
        choices=[backend.value for backend in ExecutionBackend],
        default=ExecutionBackend.DOCKER.value,
        help="Execution backend [docker, modal]",
    )


def run(args: argparse.Namespace) -> None:
    main(
        repo=args.repo,
        test_ids_ls=args.test_ids,
        timeout=args.timeout,
        branch_name=args.branch_name,
        backend=args.backend,
    )


__all__ = []
