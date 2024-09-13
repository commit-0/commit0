from datasets import load_dataset
import docker
from enum import StrEnum, auto
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
from commit0.harness.execution_context import (
    Docker,
    Modal,
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
) -> None:
    """Runs the tests in a local docker container.

    1. Creates docker container.
    2. Copies ssh public key from container to local machine.
    3. Copies eval.sh from local to container.
    4. Runs evaluation and saves to {log_dir}/test_output.txt.
    5. Copies over report.json if it exists.
    """
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

    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (
            f"Error in running pytest for {spec.repo}: {e}\n"
            f"{traceback.format_exc()}\n"
            # f"Check ({logger.log_file}) for more information."
        )
        logger.error(error_msg)
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
    """Runs the tests in a remote Modal container.

    1. Creates modal container.
    2. Copies ssh public key from container to local machine.
    3. Copies eval.sh from local to container.
    4. Runs evaluation and saves to {log_dir}/test_output.txt.
    5. Copies over report.json if it exists.
    """
    import modal
    from commit0.harness.modal_utils import (
        create_sandbox,
        copy_ssh_pubkey_from_sandbox,
        copy_file_to_sandbox,
        execute_command,
    )

    # the image must exist on dockerhub
    reponame = spec.repo.split("/")[-1]
    image_name = f"wentingzhao/{reponame}"
    image = modal.Image.from_registry(image_name)

    with modal.NetworkFileSystem.ephemeral() as nfs:
        sandbox = create_sandbox(image, nfs)

        copy_ssh_pubkey_from_sandbox(sandbox)

        # copy eval file
        copy_file_to_sandbox(sandbox, nfs, eval_file, Path("/eval.sh"))

        # DBG: check if eval file properly copied
        print("checking for eval.sh")
        print(execute_command(sandbox, "ls /")[0])

        # execute tests
        output, error = execute_command(sandbox, "/bin/bash /eval.sh")
        # TODO: add timeout
        print(output)
        print(error)

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
    """Runs the pytests for repos in a dataset.

    Tests are run either locally through docker
    or remotely through Modal.
    """
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

    #run_docker(spec, logger, eval_file, timeout, log_dir)
    run_modal(spec, logger, eval_file, timeout, log_dir)
    return

    #backend = "local"
    backend = "modal"
    execution_context = None
    if ExecutionBackend(backend) == ExecutionBackend.MODAL:
        execution_context = Modal
    elif ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        execution_context = Docker
    print(backend, execution_context)

    with execution_context(spec, logger, eval_file, timeout, log_dir) as context:
        context.copy_to_remote(eval_file, Path("/eval.sh"))
        print(context.exec_run("ls /vol")[1])
        print(context.exec_run("ls /")[1])

        print(context.exec_run("cat /eval.sh")[1])

        output, timed_out, total_runtime = context.exec_run_with_timeout(
            "/bin/bash /eval.sh", timeout
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
        # exit_code, output = container.exec_run(f"test -e {report_file}", demux=True)
        exit_code, output = context.exec_run(f"test -e {report_file}")
        # Check the exit code of the command
        if exit_code == 0:
            context.copy_from_remote(report_file, Path(log_dir / "report.json"))
            context.delete_file_from_remote(report_file)

    """
    if ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        run_docker(spec, logger, eval_file, timeout, log_dir, stdout)
    elif ExecutionBackend(backend) == ExecutionBackend.MODAL:
        run_modal(spec, logger, eval_file, timeout, log_dir, stdout)
    """
    return str(log_dir)


__all__ = []
