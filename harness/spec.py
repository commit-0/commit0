import hashlib
import json
import platform
import re

from dataclasses import dataclass
from typing import Any, Union, cast

from constants import (
    RepoInstance,
)
from dockerfiles import (
    get_dockerfile_base,
    get_dockerfile_repo,
)


@dataclass
class Spec:
    """
    A dataclass that represents a test specification for a single instance of SWE-bench.
    """
    repo: str
    repo_script_list: list[str]
    eval_script_list: list[str]
    env_script_list: list[str]

    @property
    def setup_script(self):
        return "\n".join(["#!/bin/bash", "set -euxo pipefail"] + self.repo_script_list) + "\n"

    @property
    def eval_script(self):
        return "\n".join(["#!/bin/bash", "set -uxo pipefail"] + self.eval_script_list) + "\n"
        # Don't exit early because we need to revert tests at the end

    @property
    def base_image_key(self):
        return f"commit0.base:latest"

    @property
    def repo_image_key(self):
        """
        The key for the environment image is based on the hash of the environment script list.
        If the environment script list changes, the image will be rebuilt automatically.

        Note that old images are not automatically deleted, so consider cleaning up old images periodically.
        """
        hash_object = hashlib.sha256()
        hash_object.update(str(self.setup_script).encode("utf-8"))
        hash_value = hash_object.hexdigest()
        val = hash_value[:22]  # 22 characters is still very likely to be unique
        repo = self.repo.split('/')[-1]
        return f"commit0.repo.{repo}.{val}:latest".lower()

    def get_container_name(self, run_id=None):
        repo = self.repo.split('/')[-1]
        if not run_id:
            return f"commit0.eval.{repo}"
        return f"commit0.eval.{repo}.{run_id}".lower()

    @property
    def base_dockerfile(self):
        return get_dockerfile_base(self.platform)

    @property
    def repo_dockerfile(self):
        return get_dockerfile_repo(self.platform)
    
    @property
    def platform(self):
        return "linux/x86_64"


def get_specs_from_dataset(dataset: Union[list[RepoInstance], list[Spec]]) -> list[Spec]:
    """
    Idempotent function that converts a list of SWEbenchInstance objects to a list of TestSpec objects.
    """
    if isinstance(dataset[0], Spec):
        return cast(list[Spec], dataset)
    return list(map(make_test_spec, cast(list[RepoInstance], dataset)))


def make_repo_script_list(specs, repo, repo_directory, base_commit, env_name):
    """
    Create a list of bash commands to set up the repository for testing.
    This is the setup script for the instance image.
    """
    setup_commands = [
        f"git clone -o origin https://github.com/{repo} {repo_directory}",
        f"chmod -R 777 {repo_directory}",  # So nonroot user can run tests
        f"cd {repo_directory}",
        f"git reset --hard {base_commit}",
        # Remove the remote so the agent won't see newer commits.
        f"git remote remove origin",
        f"uv venv --python {specs['python']}",
        "source .venv/bin/activate",
        f'which python',
    ]

    # Run pre-install set up if provided
    if "pre_install" in specs and specs["pre_install"] is not None:
        for pre_install in specs["pre_install"]:
            if "apt-get install" in pre_install and "-y" not in pre_install:
                pre_install = pre_install.replace("apt-get install", "apt-get install -y --no-install-recommends")
            elif "apt install" in pre_install and "-y" not in pre_install:
                pre_install = pre_install.replace("apt install", "apt install -y --no-install-recommends")
            setup_commands.append(pre_install)

    # Install dependencies
    if "packages" in specs and specs["packages"] is not None:
        for package in specs["packages"]:
            cmd = f"uv pip install -r {package}"
            setup_commands.append(cmd)

    # Install additional packages if specified
    if "pip_packages" in specs and specs["pip_packages"] is not None:
        pip_packages = [f"\"{one}\"" for one in specs["pip_packages"]]
        pip_packages = " ".join(pip_packages)
        cmd = f"uv pip install {pip_packages}"
        setup_commands.append(cmd)

    if "install" in specs and specs["install"] is not None:
        if specs["install"].startswith("pip"):
            install = "uv " + specs["install"]
        else:
            raise ValueError(f"install command should always start with pip, but you have {specs['install']}")
        setup_commands.append(install)
    return setup_commands


def make_env_script_list(instance, env_name):
    """
    Creates the list of commands to set up the uv environment for testing.
    This is the setup script for the environment image.
    """
    specs = instance["docker_setup"]
    HEREDOC_DELIMITER = "EOF_59812759871"
    reqs_commands = [
    ]

    return reqs_commands


def make_eval_script_list(instance, env_name, repo_directory, base_commit):
    """
    Run the tests.
    """
    specs = instance["docker_setup"]
    HEREDOC_DELIMITER = "EOF_114329324912"
    reset_tests_command = f"git checkout {base_commit}"
    test_command = specs["test_cmd"]
    eval_commands = [
        f"git config --global --add safe.directory {repo_directory}",  # for nonroot user
        f"cd {repo_directory}",
        # This is just informational, so we have a record
        f"git status",
        f"git show",
        f"git diff {base_commit}",
        "source .venv/bin/activate",
    ]
    eval_commands += [
        reset_tests_command,
        test_command,
        reset_tests_command,  # Revert tests after done, leave the repo in the same state as before
    ]
    return eval_commands


def make_spec(instance: RepoInstance) -> Spec:
    if isinstance(instance, Spec):
        return instance
    repo = instance["repo"]
    base_commit = instance["base_commit"]

    env_name = "testbed"
    repo_directory = f"/{env_name}"
    specs = instance['docker_setup']

    repo_script_list = make_repo_script_list(specs, repo, repo_directory, base_commit, env_name)
    env_script_list = make_env_script_list(instance, env_name)
    eval_script_list = make_eval_script_list(
        instance, env_name, repo_directory, base_commit
    )

    return Spec(
        repo=repo,
        env_script_list=env_script_list,
        repo_script_list=repo_script_list,
        eval_script_list=eval_script_list,
    )
