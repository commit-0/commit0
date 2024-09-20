import git
import os
import sys
import traceback
from datasets import load_dataset
from pathlib import Path

from typing import Iterator
from commit0.harness.constants import (
    EVAL_BACKENDS,
    Files,
    RUN_PYTEST_LOG_DIR,
    RepoInstance,
)
from commit0.harness.spec import make_spec
from commit0.harness.utils import (
    EvaluationError,
    get_hash_string,
    generate_patch_between_commits,
    setup_logger,
    close_logger,
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
    repo_or_repo_dir: str,
    branch: str,
    test_ids: str,
    backend: str,
    timeout: int,
    num_cpus: int,
    rebuild_image: bool,
    verbose: int,
) -> None:
    """Runs the pytests for repos in a dataset.

    Tests are run either locally through docker
    or remotely through Modal.
    """
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    spec = None
    example = None
    repo_name = None
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_or_repo_dir.endswith("/"):
            repo_or_repo_dir = repo_or_repo_dir[:-1]
        if repo_name in os.path.basename(repo_or_repo_dir):
            spec = make_spec(example)
            break
    assert spec is not None, "No spec available"
    assert example is not None, "No example available"
    assert repo_name is not None, "No repo available"

    hashed_test_ids = get_hash_string(test_ids)
    # set up logging
    log_dir = RUN_PYTEST_LOG_DIR / repo_name / branch / hashed_test_ids
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run_pytest.log"
    logger = setup_logger(repo_name, log_file, verbose=verbose)

    try:
        local_repo = git.Repo(repo_or_repo_dir)
        logger.info(f"Loaded a git repo from {repo_or_repo_dir}")
    except git.exc.NoSuchPathError:  # type: ignore
        repo_dir = os.path.join(base_dir, repo_name)
        logger.error(f"{repo_or_repo_dir} is not a git dir, trying {repo_dir} again")
        try:
            local_repo = git.Repo(repo_dir)
            logger.info(f"Retried succeeded. Loaded a git repo from {repo_dir}")
        except git.exc.NoSuchPathError:  # type: ignore
            raise Exception(
                f"{repo_dir} and {repo_or_repo_dir} are not git directories.\nUsage: commit0 test {{repo_dir}} {{branch}} {{test_ids}}"
            )
        except Exception as e:
            raise e
    if branch == "reference":
        commit_id = example["reference_commit"]
    else:
        try:
            local_repo.git.checkout(branch)
            local_branch = local_repo.branches[branch]
            commit_id = local_branch.commit.hexsha
        except Exception as e:
            raise Exception(f"Problem checking out branch {branch}.\n{e}")
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
        logger.info("Runnning on Modal")
        execution_context = Modal
    elif ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        logger.info("Runnning locally")
        execution_context = Docker
    else:
        raise ValueError(
            f"Evaluation must be from {', '.join(EVAL_BACKENDS)}, but {backend} is provided."
        )

    files_to_copy = Files(
        eval_script={"src": eval_file, "dest": Path("/eval.sh")},
        patch={"src": patch_file, "dest": Path("/patch.diff")},
    )
    files_to_collect = [
        "report.json",
        "coverage.json",
        "pytest_exit_code.txt",
        "test_output.txt",
    ]

    try:
        with execution_context(
            spec, logger, timeout, num_cpus, log_dir, files_to_copy, files_to_collect, rebuild_image
        ) as context:
            output, timed_out, total_runtime = context.exec_run_with_timeout(
                "/bin/bash /eval.sh"
            )
            if timed_out:
                raise EvaluationError(
                    repo_name,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )
        close_logger(logger)
        if verbose > 0:
            test_output = Path(log_dir / "test_output.txt")
            print(test_output.read_text())
        pytest_exit_code = Path(log_dir / "pytest_exit_code.txt").read_text().strip()
        sys.exit(int(pytest_exit_code))
    except EvaluationError as e:
        error_msg = (
            f"Error in running pytest for {repo_name}: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({log_file}) for more information."
        )
        raise EvaluationError(repo_name, error_msg, logger)
    except Exception as e:
        error_msg = (
            f"General error: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({log_file}) for more information."
        )
        raise RuntimeError(error_msg)


__all__ = []
