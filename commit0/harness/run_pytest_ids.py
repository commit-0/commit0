from datasets import load_dataset
from enum import StrEnum, auto
import traceback
from pathlib import Path

from typing import Iterator
from git import Repo
from commit0.harness.constants import RUN_PYTEST_LOG_DIR, RepoInstance
from commit0.harness.docker_build import (
    setup_logger,
)
from commit0.harness.spec import make_spec
from commit0.harness.utils import (
    EvaluationError,
    extract_test_output,
    get_hash_string,
    get_ip,
)
from commit0.harness.execution_context import (
    Docker,
    Modal,
)


class ExecutionBackend(StrEnum):
    LOCAL = auto()
    MODAL = auto()


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
    )
    eval_file = Path(log_dir / "eval.sh")
    eval_file.write_text(eval_script)

    # Not sure how to appease typechecker
    execution_context = Docker
    if ExecutionBackend(backend) == ExecutionBackend.MODAL:
        execution_context = Modal
    elif ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        execution_context = Docker

    try:
        with execution_context(spec, logger, eval_file, timeout, log_dir) as context:
            output, timed_out, total_runtime = context.exec_run_with_timeout(
                "/bin/bash /eval.sh", timeout
            )
            logger.info(output)
            test_output = extract_test_output(
                output, "--json-report --json-report-file=report.json"
            )
            context.write_test_output(test_output, timed_out)
            print(test_output)
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
    import os
    os.system(f"cat {log_file}")
    return str(log_dir)


__all__ = []
