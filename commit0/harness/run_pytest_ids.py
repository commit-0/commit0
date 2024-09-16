from datasets import load_dataset
import traceback
from pathlib import Path

from typing import Iterator
from git import Repo
from commit0.harness.constants import (
    EVAL_BACKENDS,
    Files,
    RUN_PYTEST_LOG_DIR,
    RepoInstance,
)
from commit0.harness.docker_build import (
    setup_logger,
)
from commit0.harness.spec import make_spec
from commit0.harness.utils import (
    EvaluationError,
    extract_test_output,
    get_hash_string,
    generate_patch_between_commits,
)
from commit0.harness.execution_context import (
    ExecutionBackend,
    Docker,
    Modal,
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

    local_repo = Repo(f"{base_dir}/{repo}")
    if branch == "reference":
        commit_id = example["reference_commit"]
    else:
        local_branch = local_repo.branches[branch]
        commit_id = local_branch.commit.hexsha
    patch = generate_patch_between_commits(
        local_repo, example["base_commit"], commit_id
    )
    patch_file = Path(log_dir / "patch.diff")
    patch_file.write_text(patch)

    # make eval file
    eval_script = spec.eval_script.format(test_ids=test_ids)
    eval_file = Path(log_dir / "eval.sh")
    eval_file.write_text(eval_script)

    if ExecutionBackend(backend) == ExecutionBackend.MODAL:
        execution_context = Modal
    elif ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        execution_context = Docker
    else:
        raise ValueError(
            f"Evaluation must be from {', '.join(EVAL_BACKENDS)}, but {backend} is provided."
        )

    files_to_copy = Files(
        eval_script={"src": eval_file, "dest": Path("/eval.sh")},
        patch={"src": patch_file, "dest": Path("/patch.diff")},
    )

    try:
        with execution_context(
            spec, logger, timeout, log_dir, files_to_copy
        ) as context:
            output, timed_out, total_runtime = context.exec_run_with_timeout(
                "/bin/bash /eval.sh"
            )
            logger.info(output)
            test_output = extract_test_output(
                output, "--json-report --json-report-file=report.json"
            )
            context.write_test_output(test_output, timed_out)
            print(test_output)
    except EvaluationError as e:
        error_msg = (
            f"Error in running pytest for {repo}: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({log_file}) for more information."
        )
        raise EvaluationError(repo, error_msg, logger)
    except Exception as e:
        error_msg = (
            f"General error: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({log_file}) for more information."
        )
        raise RuntimeError(error_msg)
    return str(log_dir)


__all__ = []
