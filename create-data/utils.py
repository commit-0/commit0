import contextlib
import difflib
import logging
import os
import shutil
import subprocess
import sys
import pytest
import venv
from glob import glob
from typing import Callable, Iterator, Optional

import ast
import astor
import git
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
    def __init__(self, owner: str, name: str, organization: str = "spec2repo", setup: [str] = [], token: Optional[str] = None):
        """
        Init to retrieve target repository and create ghapi tool

        Args:
            owner (str): owner of target repository
            name (str): name of target repository
            token (str): github token
        """
        self.name = name
        self.token = token
        self.api = GhApi(token=token)
        self.repo = self.call_api(self.api.repos.get, owner=organization, repo=name)
        if self.repo is None:
            self.repo = self.call_api(self.api.repos.create_fork, owner=owner, repo=name, organization=organization)
        self.owner = organization
        self.cwd = os.getcwd()
        self.clone_repo(setup=setup)

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

    def clone_repo(self, tmp_dir: str = './tmp/', setup: str = []) -> None:
        """
        Clone repo into a temporary directory

        Args:
            tmp_dir (str): which temporary directory to clone the repo to
        Return:
            None
        """
        clone_url = self.repo.clone_url
        self.clone_dir = os.path.abspath(os.path.join(tmp_dir, self.name))
        if os.path.exists(self.clone_dir):
            self.remove_local_repo(self.clone_dir)
        logger.info(f"cloning {clone_url} into {self.clone_dir}")
        with open(os.devnull, 'w') as devnull:
            subprocess.run(["git", "clone", clone_url, self.clone_dir], check=True, stdout=devnull, stderr=devnull)
        env_dir = os.path.join(self.clone_dir, 'venv')
        venv.create(env_dir, with_pip=True)
        logger.info(f"Virtual environment created at {env_dir}")
        os.chdir(self.clone_dir)
        for one in setup:
            one = one.strip().split(' ')
            cmd = os.path.join(env_dir, 'bin', one[0])
            cmd = ' '.join([cmd] + one[1:])
            logger.info(f"Executing {cmd}")
            os.system(cmd)
        os.chdir(self.cwd)

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
    """
    Class to replace method code with NotImplementedError
    """
    def __init__(self, removal_method):
        self.removal_method = removal_method

    def visit_FunctionDef(self, node):
        transform = node
        print(f"Processing function: {node.name}")

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

        if self.removal_method == "all":
            if docstring_node:
                node.body = [docstring_node, not_implemented_error_node]
            else:
                node.body = [not_implemented_error_node]
        elif self.removal_method == "docstring":
            if docstring_node:
                node.body = [docstring_node, not_implemented_error_node]
        else:
            raise NotImplementedError(f"Removal method {self.removal_method} is not implemented")
        return ast.copy_location(transform, node)


def _find_files_to_edit(base_dir: str) -> list[str]:
    """
    Identify files to remove content by heuristics.
    We assume source code is under [lib]/[lib] or [lib]/src.
    We exclude test code. This function would not work
    if test code doesn't have its own directory.

    Args:
        base_dir (str): the path to local library.

    Return:
        files (list[str]): a list of files to be edited.
    """
    name = os.path.basename(base_dir)
    path_src = os.path.join(base_dir, name, "**", "*.py")
    files = glob(path_src, recursive=True)
    path_test = os.path.join(base_dir, name, "**", "test*", "**", "*.py")
    test_files = glob(path_test, recursive=True)
    files = list(set(files) - set(test_files))
    return files

def generate_base_commit(repo: Repo, commit: str, branch_name: str = "spec2repo", removal: str = "all") -> str:
    """
    Generate a base commit by removing all function contents

    Args:
        repo (Repo): from which repo to generate the base commit
        commit (str): from which commit to generate the base commit
        branch_name (str): the branch name of the base commit
    Return:
        collected_tests (list[str]): a list of test function names
    """
    # check if base commit has already been generated
    local_repo = git.Repo(repo.clone_dir)
    remote = local_repo.remote()
    remote.fetch()
    exists = False
    for ref in local_repo.refs:
        if ref.name.endswith(f"/{branch_name}"):
            branch_name = ref.name
            exists = True
            break
    if exists:
        branch = local_repo.refs[branch_name]
        if branch.commit.message == "Generated base commit.":
            logger.info(f"Base commit has already been created.")
            return branch.commit.hexsha
        else:
            raise ValueError(f"{branch_name} exists but it's not the base commit")
    else:
        logger.info(f"Creating the base commit {repo.owner}/{repo.name}")
        local_repo.git.checkout('-b', branch_name)
        files = _find_files_to_edit(repo.clone_dir)
        for f in files:
            tree = astor.parse_file(f)
            tree = RemoveMethod(removal).visit(tree)
            open(f, "w").write(astor.to_source(tree))
            local_repo.git.add(f)
        dummy_test_file = os.path.join(repo.clone_dir, "dummy.txt")
        with open(dummy_test_file, 'w'):
            pass
        local_repo.git.add(dummy_test_file)
        commit = local_repo.index.commit("Generated base commit.")
        origin = local_repo.remote(name='origin')
        origin.push(branch_name)
        os.chdir(repo.clone_dir)
        return commit.hexsha


def retrieve_commit_time(repo: Repo, commit: str) -> str:
    """
    Generate a base commit by removing all function contents

    Args:
        repo (Repo): repository of the commit
        commit (str): which commit to retrieve creation time
    Return:
        commit_time (str): time at which the commit was created
    """
    commit_info = repo.call_api(repo.api.repos.get_commit, owner=repo.owner, repo=repo.name, ref=commit)
    commit_time = commit_info.commit.author.date
    return commit_time

def extract_patches(repo: Repo, commit1: str, commit2: str) -> tuple[str, str]:
    """
    Generate both the gold patch and a dummy test patch (required by SWE-bench)

    Args:
        repo: which repo to generate patches
        commit1: commit before changes
        commit2: commit after changes

    Return:
        patches (tuple[str, str]): the gold patch and a dummy test patch
    """
    files = _find_files_to_edit(repo.clone_dir)
    local_repo = git.Repo(repo.clone_dir)
    befores = []
    local_repo.git.checkout(commit1)
    for f in files:
        with open(f, 'r') as fin:
            befores.append(fin.readlines())
    afters = []
    local_repo.git.checkout(commit2)
    for f in files:
        with open(f, 'r') as fin:
            afters.append(fin.readlines())
    diffs = []
    for before, after, f in zip(befores, afters, files):
        shortened_f = f.replace(repo.clone_dir, '')
        if shortened_f.startswith('/'):
            shortened_f = shortened_f[1:]
        diff = difflib.unified_diff(
            before,
            after,
            fromfile='a/'+shortened_f,
            tofile='b/'+shortened_f,
        )
        diffs.append(''.join(diff))
    patch = '\n'.join(diffs)
    dummy_f = "dummy.txt"
    test_patch = difflib.unified_diff(
        [],
        ['Dummy TestPatch'],
        fromfile='a/'+dummy_f,
        tofile='b/'+dummy_f,
    )
    test_patch = ''.join(test_patch)+'\n' # patch file needs a new line at the end
    return patch, test_patch

def extract_test_names(repo: Repo, commit: str) -> list[str]:
    """
    Extract all test function names

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
