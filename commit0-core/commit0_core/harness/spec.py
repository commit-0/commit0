import hashlib
from dataclasses import dataclass
from typing import Union, cast, Optional

from commit0.harness.constants import (
    RepoInstance,
)
from commit0.harness.dockerfiles import (
    get_dockerfile_base,
    get_dockerfile_repo,
)


@dataclass
class Spec:
    """A dataclass that represents a test specification for a single instance of SWE-bench."""

    repo: str
    # repo dir on docker
    repo_directory: str
    repo_script_list: list[str]
    eval_script_list: list[str]

    @property
    def setup_script(self) -> str:
        return (
            "\n".join(["#!/bin/bash", "set -euxo pipefail"] + self.repo_script_list)
            + "\n"
        )

    @property
    def eval_script(self) -> str:
        return (
            "\n".join(["#!/bin/bash", "set -uxo pipefail"] + self.eval_script_list)
            + "\n"
        )
        # Don't exit early because we need to revert tests at the end

    @property
    def base_image_key(self) -> str:
        return "commit0.base:latest"

    @property
    def repo_image_key(self) -> str:
        """The key for the environment image is based on the hash of the environment script list.
        If the environment script list changes, the image will be rebuilt automatically.

        Note that old images are not automatically deleted, so consider cleaning up old images periodically.
        """
        hash_object = hashlib.sha256()
        hash_object.update(str(self.setup_script).encode("utf-8"))
        hash_value = hash_object.hexdigest()
        val = hash_value[:22]  # 22 characters is still very likely to be unique
        repo = self.repo.split("/")[-1]
        # this is the image name created locally
        # once this image created, it will be tagged with repo_image_tag
        return f"commit0.repo.{repo}.{val}:v0".lower()

    @property
    def repo_image_tag(self) -> str:
        """Repo image tag that will be used throughout."""
        repo = self.repo.split("/")[-1]
        return f"wentingzhao/{repo}:v0".lower()

    def get_container_name(self, run_id: Optional[str] = None) -> str:
        repo = self.repo.split("/")[-1]
        if not run_id:
            return f"commit0.eval.{repo}"
        return f"commit0.eval.{repo}.{run_id}".lower()

    @property
    def base_dockerfile(self) -> str:
        return get_dockerfile_base(self.platform)

    @property
    def repo_dockerfile(self) -> str:
        return get_dockerfile_repo(self.platform)

    @property
    def platform(self) -> str:
        return "linux/x86_64"


def get_specs_from_dataset(
    dataset: Union[list[RepoInstance], list[Spec]],
) -> list[Spec]:
    """Idempotent function that converts a list of SWEbenchInstance objects to a list of TestSpec objects."""
    if isinstance(dataset[0], Spec):
        return cast(list[Spec], dataset)
    return list(map(make_spec, cast(list[RepoInstance], dataset)))


def make_repo_script_list(instance: RepoInstance, repo_directory: str) -> list[str]:
    """Create a list of bash commands to set up the repository for testing.
    This is the setup script for the instance image.
    """
    specs = instance["setup"]
    repo = instance["repo"]
    env_setup_commit = instance["reference_commit"]
    base_commit = instance["base_commit"]

    setup_commands = [
        f"git clone -o origin https://github.com/{repo} {repo_directory}",
        f"chmod -R 777 {repo_directory}",  # So nonroot user can run tests
        f"cd {repo_directory}",
        f"git reset --hard {env_setup_commit}",
        # Remove the remote so the agent won't see newer commits.
        "git remote remove origin",
        f"uv venv --python {specs['python']}",
        "source .venv/bin/activate",
        "which python",
    ]

    # Run pre-install set up if provided
    if "pre_install" in specs and specs["pre_install"] is not None:
        for pre_install in specs["pre_install"]:
            if "apt-get install" in pre_install and "-y" not in pre_install:
                pre_install = pre_install.replace(
                    "apt-get install", "apt-get install -y --no-install-recommends"
                )
            elif "apt install" in pre_install and "-y" not in pre_install:
                pre_install = pre_install.replace(
                    "apt install", "apt install -y --no-install-recommends"
                )
            setup_commands.append(pre_install)

    # Install dependencies
    if "packages" in specs and specs["packages"] is not None:
        for package in specs["packages"]:
            cmd = f"uv pip install -r {package}"
            setup_commands.append(cmd)

    # Install additional packages if specified
    if "pip_packages" in specs and specs["pip_packages"] is not None:
        pip_packages = [f'"{one}"' for one in specs["pip_packages"]]
        pip_packages = " ".join(pip_packages)
        cmd = f"uv pip install {pip_packages}"
        setup_commands.append(cmd)

    if "install" in specs and specs["install"] is not None:
        if specs["install"].startswith("pip"):
            install = "uv " + specs["install"]
        else:
            raise ValueError(
                f"install command should always start with pip, but you have {specs['install']}"
            )
        setup_commands.append(install)
    setup_commands.append(
        "uv pip install -U pytest pytest-cov coverage pytest-json-report"
    )
    setup_commands.append(f"git reset --hard {base_commit}")
    return setup_commands


def make_eval_script_list(instance: RepoInstance, repo_directory: str) -> list[str]:
    """Run the tests."""
    eval_script_list = [
        f"cd {repo_directory}",
        "source .venv/bin/activate",
        f"git reset --hard {instance['base_commit']}",
        "git apply --allow-empty -v /patch.diff",
        "git status",
        f"{instance['test']['test_cmd']} --json-report --json-report-file=report.json --continue-on-collection-errors{{coverage}} {{test_ids}} > test_output.txt 2>&1",
        "echo $? > pytest_exit_code.txt",
    ]
    return eval_script_list


def make_spec(instance: RepoInstance) -> Spec:
    if isinstance(instance, Spec):
        return instance

    repo_directory = "/testbed"

    repo_script_list = make_repo_script_list(instance, repo_directory)
    eval_script_list = make_eval_script_list(instance, repo_directory)

    return Spec(
        repo=instance["repo"],
        repo_directory=repo_directory,
        repo_script_list=repo_script_list,
        eval_script_list=eval_script_list,
    )


__all__ = []
