import git
import git.exc
import hashlib
import logging
import socket
import os
import time
import requests
import subprocess
import pwd
from typing import Optional, Tuple

from fastcore.net import HTTP404NotFoundError, HTTP403ForbiddenError  # type: ignore
from ghapi.core import GhApi
from commit0.harness.constants import EVAL_BACKENDS


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
            return "\n".join(out)
        if append:
            out.append(one)
    return ""


def clone_repo(
    clone_url: str, clone_dir: str, commit: str, logger: logging.Logger
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
    commit : str
        The commit hash or branch/tag name to checkout.
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

    logger.info(f"Checking out {commit}")
    try:
        repo.git.checkout(commit)
    except git.exc.GitCommandError as e:
        raise RuntimeError(f"Failed to check out {commit}: {e}")

    return repo


def create_branch(repo: git.Repo, branch: str, logger: logging.Logger) -> None:
    """Create a new branch or switch to an existing branch.

    Parameters
    ----------
    repo : git.Repo
        The repository object.
    branch : str
        The name of the branch to create or switch to.
    logger : logging.Logger
        The logger object.

    Returns
    -------
    None

    Raises
    ------
    RuntimeError
        If creating or switching to the branch fails.

    """
    try:
        # Check if the branch already exists
        if branch in repo.heads:
            logger.info(f"Branch '{branch}' already exists. Checking out the branch.")
            repo.git.checkout(branch)
        else:
            logger.info(f"Creating new branch '{branch}' and checking out the branch.")
            repo.git.checkout("-b", branch)
    except git.exc.GitCommandError as e:
        raise RuntimeError(f"Failed to create or switch to branch '{branch}': {e}")


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


def generate_patch_between_commits(repo: git.Repo, old_commit: str, new_commit: str) -> str:
    """
    Generate a patch string by comparing two specified commits.

    Args:
        repo (git.Repo): An instance of the git.Repo object representing the repository.
        old_commit (str): The hash or reference to the old commit.
        new_commit (str): The hash or reference to the new commit.

    Returns:
        patch (str): A string containing the patch in the diff format between the two commits

    Raises:
        git.GitCommandError: If there is an error while running git commands.
    """
    try:
        patch = repo.git.diff(old_commit, new_commit, '--', '.', ':(exclude)spec.pdf')
        return patch+'\n\n'
    except git.GitCommandError as e:
        raise Exception(f"Error generating patch: {e}")

__all__ = []
