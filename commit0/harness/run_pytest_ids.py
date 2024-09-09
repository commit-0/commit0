import argparse
import docker
import os
import traceback
import yaml
from pathlib import Path

from commit0.harness.constants import (
    RUN_PYTEST_LOG_DIR
)
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
from commit0.harness.spec import make_spec
from commit0.harness.utils import (
    EvaluationError,
    extract_test_output,
    get_hash_string,
)


def main(repo: str, test_ids: list[str], timeout: int, branch_name: str):
    with open("config.yml", 'r') as file:
        data = yaml.safe_load(file)
    spec = make_spec(data[repo])
    test_ids = " ".join(test_ids)
    hashed_test_ids = get_hash_string(test_ids)

    # set up logging
    log_dir = RUN_PYTEST_LOG_DIR / repo / hashed_test_ids
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run_pytest.log"
    logger = setup_logger(repo, log_file)

    # make eval file
    eval_script = spec.eval_script.format(local_repo=data[repo]['local_path'], branch_name=branch_name, test_ids=test_ids)
    eval_file = Path(log_dir / "eval.sh")
    eval_file.write_text(eval_script)

    client = docker.from_env()
    container = None
    try:
        container = create_container(
            client=client,
            image_name=spec.repo_image_key,
            container_name=spec.get_container_name(),
            logger=logger
        )
        container.start()
        copy_ssh_pubkey_from_container(container)

        logger.info(
            f"Eval script written to {eval_file}; copying to container..."
        )
        copy_to_container(container, eval_file, Path("/eval.sh"))

        # Run eval script, write output to logs
        output, timed_out, total_runtime = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout)
        logger.info(output)

        test_output = extract_test_output(output, "--json-report --json-report-file=report.json")
        # stdout might be more straightforward
        print(test_output)
        test_output_path = log_dir / "test_output.txt"
        with open(test_output_path, "w") as f:
            f.write(test_output)
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    repo,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )

        # copy back report.json if there is any
        report_file = Path(spec.repo_directory) / "report.json"
        # Run the test command inside the container to check if the file exists
        exit_code, output = container.exec_run(f'test -e {report_file}', demux=True)
        # Check the exit code of the command
        if exit_code == 0:
            copy_from_container(container, report_file, Path(log_dir / "report.json"))
            delete_file_from_container(container, report_file)

    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (f"Error in running pytest for {repo}: {e}\n"
                     f"{traceback.format_exc()}\n"
                     f"Check ({logger.log_file}) for more information.")
        logger.error(error_msg)
    finally:
        # Remove repo container + image, close logger
        cleanup_container(client, container, logger)
        close_logger(logger)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=str, help="which repo to run unit tests")
    parser.add_argument(
        "--test_ids", 
        type=str, 
        nargs='+',
        help="which test ids / files / directories"
    )
    parser.add_argument("--branch_name", type=str, help="which git branch to run unit tests")
    parser.add_argument(
        "--timeout", type=int, default=1_800, help="Timeout (in seconds) for running tests for each instance"
        )
    args = parser.parse_args()
    main(**vars(args))
