import git
import git.exc
import hashlib
import logging
import os
import time
import sys
from pathlib import Path
from typing import Optional, Union

from fastcore.net import HTTP404NotFoundError, HTTP403ForbiddenError  # type: ignore
from ghapi.core import GhApi


class EvaluationError(Exception):
    def __init__(self, repo: str, message: str, logger: logging.Logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.repo = repo
        self.log_file = ""  # logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Evaluation error for {self.repo}: {self.super_str}\n"
            f"Check ({self.log_file}) for more information."
        )


def setup_logger(
    repo: str, log_file: Path, mode: str = "w", verbose: int = 1
) -> logging.Logger:
    """Used for logging the build process of images and running containers.
    It writes logs to the log file.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"{repo}.{log_file.name}")
    handler = logging.FileHandler(log_file, mode=mode)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if verbose == 2:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    setattr(logger, "log_file", log_file)
    return logger


def close_logger(logger: logging.Logger) -> None:
    """Closes all handlers associated with the given logger to prevent too many open files."""
    # To avoid too many open files
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)


def get_hash_string(input_string: str) -> str:
    # Create a new SHA-256 hash object
    sha256 = hashlib.sha256()
    # Update the hash object with the bytes of the input string
    sha256.update(input_string.encode("utf-8"))
    # Obtain the hexadecimal digest of the hash
    hash_hex = sha256.hexdigest()[:22]
    return hash_hex


def extract_test_output(ss: str, pattern: str) -> str:
    s = ss.split("\n")
    out = []
    append = False
    for one in s:
        if one.startswith("+") and pattern in one:
            append = True
        # the next command started here, so we finished reading test output
        elif append and one.startswith("+"):
            # remove the first element "+ {command}"
            out = out[1:]
            return "\n".join(out).strip()
        if append:
            out.append(one)
    return ""


def clone_repo(
    clone_url: str, clone_dir: str, branch: str, logger: logging.Logger
) -> git.Repo:
    """Clone repo into the specified directory if it does not already exist.

    If the repository already exists in the specified directory,
    it fetches the latest changes and checks out the specified commit.

    Parameters
    ----------
    clone_url : str
        URL of the repository to clone.
    clone_dir : str
        Directory where the repository will be cloned.
    branch : str
        The branch/tag name to checkout.
    logger : logging.Logger
        The logger object.

    Returns
    -------
    git.Repo
        The cloned repository object.

    Raises
    ------
    RuntimeError
        If cloning or checking out the repository fails.

    """
    # Check if the repository already exists
    if os.path.exists(clone_dir):
        logger.info(f"Repository already exists at {clone_dir}. Fetching updates.")
        try:
            repo = git.Repo(clone_dir)
            repo.git.fetch()
        except git.exc.GitCommandError as e:
            raise RuntimeError(f"Failed to fetch updates for repository: {e}")
    else:
        logger.info(f"Cloning {clone_url} into {clone_dir}")
        try:
            repo = git.Repo.clone_from(clone_url, clone_dir)
        except git.exc.GitCommandError as e:
            raise RuntimeError(f"Failed to clone repository: {e}")

    try:
        repo.git.checkout(branch)
    except git.exc.GitCommandError as e:
        raise RuntimeError(f"Failed to check out {branch}: {e}")

    return repo


def create_repo_on_github(
    organization: str, repo: str, logger: logging.Logger, token: Optional[str] = None
) -> None:
    api = GhApi(token=token)
    while True:
        try:
            api.repos.get(owner=organization, repo=repo)  # type: ignore
            logger.info(f"{organization}/{repo} already exists")
            break
        except HTTP403ForbiddenError:
            while True:
                rl = api.rate_limit.get()  # type: ignore
                logger.info(
                    f"Rate limit exceeded for the current GitHub token,"
                    f"waiting for 5 minutes, remaining calls: {rl.resources.core.remaining}"
                )
                if rl.resources.core.remaining > 0:
                    break
                time.sleep(60 * 5)
        except HTTP404NotFoundError:
            api.repos.create_in_org(org=organization, name=repo)  # type: ignore
            logger.info(f"Created {organization}/{repo} on GitHub")
            break


def generate_patch_between_commits(
    repo: git.Repo, old_commit: str, new_commit: str
) -> str:
    """Generate a patch string by comparing two specified commits.

    Args:
    ----
        repo (git.Repo): An instance of the git.Repo object representing the repository.
        old_commit (str): The hash or reference to the old commit.
        new_commit (str): The hash or reference to the new commit.

    Returns:
    -------
        patch (str): A string containing the patch in the diff format between the two commits

    Raises:
    ------
        git.GitCommandError: If there is an error while running git commands.

    """
    try:
        patch = repo.git.diff(
            old_commit, new_commit, "--", ".", ":(exclude)spec.pdf.bz2"
        )
        return patch + "\n\n"
    except git.GitCommandError as e:
        raise Exception(f"Error generating patch: {e}")


def get_active_branch(repo_path: Union[str, Path]) -> str:
    """Retrieve the current active branch of a Git repository.

    Args:
    ----
        repo_path (Path): The path to git repo.

    Returns:
    -------
        str: The name of the active branch.

    Raises:
    ------
        Exception: If the repository is in a detached HEAD state.

    """
    repo = git.Repo(repo_path)
    try:
        # Get the current active branch
        branch = repo.active_branch.name
    except TypeError as e:
        raise Exception(
            f"{e}\nThis means the repository is in a detached HEAD state. "
            "To proceed, please specify a valid branch by using --branch {branch}."
        )

    return branch


__all__ = []
