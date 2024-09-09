import getpass
import git
import hashlib
import logging
import socket
import os
from commit0.harness.constants import EVAL_BACKENDS


class EvaluationError(Exception):
    def __init__(self, repo, message, logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.repo = repo
        self.log_file = logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Evaluation error for {self.repo}: {self.super_str}\n"
            f"Check ({self.log_file}) for more information."
        )


def get_ip(backend: str):
    if backend not in EVAL_BACKENDS:
        raise ValueError(f"We only support evaluation backends = {EVAL_BACKENDS}, but you provided {backend}")
    if backend == "modal":
        try:
            response = requests.get('https://api.ipify.org?format=json')
            response.raise_for_status()
            ip = response.json()['ip']
        except requests.RequestException as e:
            raise Exception(f"Cannot get the public IP address.\n{e}")
    elif backend == "local":
        try:
            # Connect to a public DNS server, then get the local socket name
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception as e:
            ip = '127.0.0.1'  # Fallback to localhost IP
        finally:
            s.close()
    return ip


def get_user():
    return getpass.getuser()


def get_hash_string(input_string):
    # Create a new SHA-256 hash object
    sha256 = hashlib.sha256()
    # Update the hash object with the bytes of the input string
    sha256.update(input_string.encode("utf-8"))
    # Obtain the hexadecimal digest of the hash
    hash_hex = sha256.hexdigest()[:22]
    return hash_hex


def extract_test_output(s, pattern):
    s = s.split("\n")
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


def clone_repo(clone_url: str, clone_dir: str, commit: str, logger: logging.Logger) -> git.Repo:
    """Clone repo into the specified directory if it does not already exist.

    If the repository already exists in the specified directory,
    it fetches the latest changes and checks out the specified commit.

    Parameters:
    ----------
    clone_url : str
        URL of the repository to clone.
    clone_dir : str
        Directory where the repository will be cloned.
    commit : str
        The commit hash or branch/tag name to checkout.
    logger : logging.Logger
        The logger object.

    Returns:
    -------
    git.Repo
        The cloned repository object.

    Raises:
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

    Parameters:
    ----------
    repo : git.Repo
        The repository object.
    branch : str
        The name of the branch to create or switch to.
    logger : logging.Logger
        The logger object.

    Returns:
    -------
    None

    Raises:
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
            repo.git.checkout('-b', branch)
    except git.exc.GitCommandError as e:
        raise RuntimeError(f"Failed to create or switch to branch '{branch}': {e}")
