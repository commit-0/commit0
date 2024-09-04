import difflib
import logging
import os
import shutil
import time
from glob import glob
from typing import Callable, Optional

import ast
import astor
import git
from ghapi.core import GhApi
from fastcore.net import HTTP404NotFoundError, HTTP403ForbiddenError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Repo:
    def __init__(self, owner: str, name: str, organization: str, head: str, token: Optional[str] = None):
        """
        Init to retrieve target repository and create ghapi tool

        Args:
            owner (str): owner of target repository
            name (str): name of target repository
            org (str): under which organization to fork repos to
            head (str): which head to set the repo to
            setup (list[str]): a list of setup steps
            token (str): github token
        """
        self.name = name
        self.owner = organization
        self.token = token
        self.api = GhApi(token=token)
        self.repo = self.call_api(self.api.repos.get, owner=organization, repo=name)
        if self.repo is None:
            self.repo = self.call_api(self.api.repos.create_fork, owner=owner, repo=name, organization=organization)
            # The API call returns immediately when the fork isn't complete. Needed to wait for a few seconds to finish.
            time.sleep(2)
        self.cwd = os.getcwd()
        if head.startswith("tags/"):
            self.commit = self.get_commit_by_tag(head)
        else:
            self.commit = head
        logger.info("Setting up a local copy of the repository.")
        self.clone_dir = os.path.abspath(os.path.join('tmp', self.name))
        self.local_repo = self.clone_repo()

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

    def clone_repo(self) -> None:
        """
        Clone repo into a temporary directory

        Return:
            None
        """
        clone_url = self.repo.clone_url
        # cleanup if the repo already exists
        self.remove_local_repo()
        logger.info(f"cloning {clone_url} into {self.clone_dir}")
        try:
            repo = git.Repo.clone_from(clone_url, self.clone_dir)
        except git.exc.GitCommandError as e:
            raise RuntimeError(f"Failed to clone repository: {e}")
        logger.info(f"checking out {self.commit}")
        try:
            repo.git.checkout(self.commit)
        except git.exc.GitCommandError as e:
            raise RuntimeError(f"Failed to check out {self.commit}: {e}")
        return repo

    def remove_local_repo(self) -> None:
        """
        Remove the cloned repository directory from the local filesystem.
        """
        if os.path.exists(self.clone_dir):
            try:
                shutil.rmtree(self.clone_dir)
            except OSError:
                os.system(f"rm -rf {self.clone_dir}")
            logger.info(f"Cleaned up the cloned repository at {self.clone_dir}")

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
    path_src = os.path.join(base_dir, 'src', name, "**", "*.py")
    files += glob(path_src, recursive=True)
    path_src = os.path.join(base_dir, 'src', "**", "*.py")
    files += glob(path_src, recursive=True)
    path_test = os.path.join(base_dir, name, "**", "test*", "**", "*.py")
    test_files = glob(path_test, recursive=True)
    files = list(set(files) - set(test_files))
    return files

def generate_base_commit(repo: Repo, base_branch_name: str = "spec2repo", removal: str = "all") -> str:
    """
    Generate a base commit by removing all function contents

    Args:
        repo (Repo): from which repo to generate the base commit
        base_branch_name (str): base of the branch name of the base commit
    Return:
        collected_tests (list[str]): a list of test function names
    """
    # check if base commit has already been generated
    remote = repo.local_repo.remote()
    remote.fetch()
    exists = False
    branch_name = f"{base_branch_name}_{removal}"
    for ref in repo.local_repo.refs:
        if ref.name.endswith(f"/{branch_name}"):
            branch_name = ref.name
            exists = True
            break
    if exists:
        branch = repo.local_repo.refs[branch_name]
        if branch.commit.message == "Commit 0":
            logger.info(f"Commit 0 has already been created.")
            return branch.commit.hexsha
        else:
            raise ValueError(f"{branch_name} exists but it's not the base commit")
    else:
        logger.info(f"Creating commit 0 {repo.owner}/{repo.name}")
        repo.local_repo.git.checkout('-b', branch_name)
        files = _find_files_to_edit(repo.clone_dir)
        for f in files:
            tree = astor.parse_file(f)
            tree = RemoveMethod(removal).visit(tree)
            open(f, "w").write(astor.to_source(tree))
            try:
                repo.local_repo.git.add(f)
            except git.exc.GitCommandError as e:
                if "paths are ignored by one of your .gitignore files" in e.stderr:
                    logger.warning(f"File {f} is ignored due to .gitignore rules and won't be added.")
                elif "is in submodule" in e.stderr:
                    logger.warning(f"File {f} is in a submodule and won't be added.")
                else:
                    raise
        base_commit = repo.local_repo.index.commit("Commit 0")
        origin = repo.local_repo.remote(name='origin')
        origin.push(branch_name)
        # go back to the starting commit
        repo.local_repo.git.checkout(repo.commit)
        return base_commit.hexsha


def extract_patch(repo: Repo, base_commit: str) -> tuple[str, str]:
    """
    Generate both the gold patch

    Args:
        repo: which repo to generate patches
        base_commit: commit before changes

    Return:
        patch (str): the gold patch
    """
    files = _find_files_to_edit(repo.clone_dir)
    befores = []
    repo.local_repo.git.checkout(base_commit)
    for f in files:
        with open(f, 'r') as fin:
            befores.append(fin.readlines())
    afters = []
    repo.local_repo.git.checkout(repo.commit)
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
    return patch

