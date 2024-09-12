from datasets import load_dataset
import docker
from enum import StrEnum, auto
import os
import traceback
from pathlib import Path
import logging

from typing import Iterator
from git import Repo
from commit0.harness.constants import RUN_PYTEST_LOG_DIR, RepoInstance
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
    LOCAL = auto()
    MODAL = auto()


def run_docker(
    spec: Spec,
    logger: logging.Logger,
    eval_file: Path,
    timeout: int,
    log_dir: Path,
    stdout: bool,
) -> str:
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
        if stdout:
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
            delete_file_from_container(container, str(report_file))
        return test_output

    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
        return error_msg
    except Exception as e:
        error_msg = (
            f"Error in running pytest for {spec.repo}: {e}\n"
            f"{traceback.format_exc()}\n"
            # f"Check ({logger.log_file}) for more information."
        )
        logger.error(error_msg)
        return error_msg
    finally:
        # Remove repo container + image, close logger
        assert container is not None
        cleanup_container(client, container, logger)
        close_logger(logger)


def run_modal(
    spec: Spec,
    logger: logging.Logger,
    eval_file: Path,
    timeout: int,
    log_dir: Path,
    stdout: bool,
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
        line = ""
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
        test_output = extract_test_output(
            output_s, "--json-report --json-report-file=report.json"
        )

        # stdout might be more straightforward
        if stdout:
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
    dataset_name: str,
    dataset_split: str,
    base_dir: str,
    repo: str,
    branch: str,
    test_ids: str,
    backend: str,
    timeout: int,
    stdout: bool,
) -> str:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    spec = None
    example = None
    for example in dataset:
        if example["repo"].endswith(repo):
            spec = make_spec(example)
            break
    assert spec is not None, "No spec available"
    assert example is not None, "No example available"

    hashed_test_ids = get_hash_string(test_ids)
    # set up logging
    log_dir = RUN_PYTEST_LOG_DIR / repo / branch / hashed_test_ids
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run_pytest.log"
    logger = setup_logger(repo, log_file)

    if branch == "reference":
        commit_id = example["reference_commit"]
    else:
        local_repo = Repo(f"{base_dir}/{repo}")
        local_branch = local_repo.branches[branch]
        commit_id = local_branch.commit.hexsha

    # make eval file
    eval_script = spec.eval_script.format(
        local_repo=f"{base_dir}/{repo}",
        commit_id=commit_id,
        test_ids=test_ids,
        ip=get_ip(backend),
        user=get_user(),
    )
    eval_file = Path(log_dir / "eval.sh")
    eval_file.write_text(eval_script)

    error_message = None
    if ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        error_message = run_docker(spec, logger, eval_file, timeout, log_dir, stdout)
    elif ExecutionBackend(backend) == ExecutionBackend.MODAL:
        run_modal(spec, logger, eval_file, timeout, log_dir, stdout)
    if error_message:
        return error_message
    return str(log_dir)


__all__ = []
