import contextlib
import logging
import os
import shutil
import subprocess
import sys
import pytest
from glob import glob
from typing import Callable, Iterator, Optional
from unidiff import PatchSet

import ast
import astor
from ghapi.core import GhApi
from fastcore.net import HTTP404NotFoundError, HTTP403ForbiddenError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def silent():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        #old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            #sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            #sys.stderr = old_stderr


class Repo:
    def __init__(self, owner: str, name: str, organization: str = "spec2repo", token: Optional[str] = None):
        """
        Init to retrieve target repository and create ghapi tool

        Args:
            owner (str): owner of target repository
            name (str): name of target repository
            token (str): github token
        """
        self.owner = owner
        self.name = name
        self.token = token
        self.api = GhApi(token=token)
        self.repo = self.call_api(self.api.repos.get, owner=organization, repo=name)
        if self.repo is None:
            self.repo = self.call_api(self.api.repos.create_fork, owner=owner, repo=name, organization=organization)
        with silent():
            self.clone_repo()

    def call_api(self, func: Callable, **kwargs) -> dict|None:
        """
        API call wrapper with rate limit handling (checks every 5 minutes if rate limit is reset)

        Args:
            func (callable): API function to call
            **kwargs: keyword arguments to pass to API function
        Return:
            values (dict): response object of `func`
        """
        while True:
            try:
                values = func(**kwargs)
                return values
            except HTTP403ForbiddenError as e:
                while True:
                    rl = self.api.rate_limit.get()
                    logger.info(
                        f"[{self.owner}/{self.name}] Rate limit exceeded for token {self.token[:10]}, "
                        f"waiting for 5 minutes, remaining calls: {rl.resources.core.remaining}"
                    )
                    if rl.resources.core.remaining > 0:
                        break
                    time.sleep(60 * 5)
            except HTTP404NotFoundError as e:
                logger.info(f"[{self.owner}/{self.name}] Resource not found {kwargs}")
                return None

    def clone_repo(self, tmp_dir: str = './tmp/') -> None:
        """
        Clone repo into a temporary directory

        Args:
            tmp_dir (str): which temporary directory to clone the repo to
        Return:
            None
        """
        clone_url = self.repo.clone_url
        self.clone_dir = os.path.join(tmp_dir, self.name)
        if os.path.exists(self.clone_dir):
            self.remove_local_repo(self.clone_dir)
        logger.info(f"cloning {clone_url} into {self.clone_dir}")
        with open(os.devnull, 'w') as devnull:
            subprocess.run(["git", "clone", clone_url, self.clone_dir], check=True, stdout=devnull, stderr=devnull)

    def remove_local_repo(self, path_to_repo: str) -> None:
        """
        Remove the cloned repository directory from the local filesystem.

        Args:
            path_to_dir (str): directory to the repo to remove
        Return:
            None
        """
        if os.path.exists(path_to_repo):
            shutil.rmtree(path_to_repo)
            logger.info(f"Cleaned up the cloned repository at {path_to_repo}")

    def get_commit_by_tag(self, tag: str) -> str:
        """
        Get commit sha for a tag

        Args:
            tag (str): to retrieve the commit of which tag
        Return:
            commit (str): sha of the commit
        """
        tag_ref = self.call_api(self.api.git.get_ref, owner=self.owner, repo=self.name, ref=tag)
        return tag_ref.object.sha


class RemoveMethod(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        transform = node

        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
            docstring_node = node.body[0]
        else:
            docstring_node = None

        not_implemented_error_node = ast.Raise(
            exc=ast.Call(
                func=ast.Name(id='NotImplementedError', ctx=ast.Load()),
                args=[ast.Constant(value="IMPLEMENT ME HERE")],
                keywords=[]
            ),
            cause=None
        )

        if docstring_node:
            node.body = [docstring_node, not_implemented_error_node]
        else:
            node.body = [not_implemented_error_node]
        return ast.copy_location(transform, node)

def generate_base_commit(repo: Repo, commit: str) -> str:
    path_src = os.path.join(repo.clone_dir, repo.name, "**", "*.py")
    files = glob(path_src, recursive=True)
    for f in files:
        tree = astor.parse_file(f)
        tree = RemoveMethod().visit(tree)
        open(f, "w").write(astor.to_source(tree))
    return files

def extract_patches(repo: Repo, commit: str) -> tuple[str, str]:
    raise NotImplementedError


def extract_test_names(repo: Repo, commit: str) -> list[str]:
    """
    extract all test function names

    Args:
        repo (Repo): test names from which repo
        commit (str): test functions from which commit
    Return:
        collected_tests (list[str]): a list of test function names
    """
    def list_pytest_functions():
        plugin = Plugin()
        # Run pytest in "collect-only" mode and use our custom plugin
        pytest.main(["--collect-only", repo.clone_dir], plugins=[plugin])
        return plugin.collected_tests

    class Plugin:
        def __init__(self):
            self.collected_tests = []

        def pytest_sessionfinish(self, session, exitstatus):
            # Collect test node IDs into the list
            for item in session.items:
                self.collected_tests.append(item.nodeid)
    with silent():
        test_names = list_pytest_functions()
    return test_names
