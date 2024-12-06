import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Union, cast, Optional

from commit0.harness.constants import (
    RepoInstance,
    SimpleInstance,
)
from commit0.harness.dockerfiles import (
    get_dockerfile_base,
    get_dockerfile_repo,
)


@dataclass
class Spec(ABC):
    """A dataclass that represents a test specification for a single instance of SWE-bench."""

    repo: str
    # repo dir on docker
    repo_directory: str
    instance: Union[RepoInstance, SimpleInstance]

    @property
    def setup_script(self) -> str:
        self.repo_script_list = self.make_repo_script_list()
        return (
            "\n".join(["#!/bin/bash", "set -euxo pipefail"] + self.repo_script_list)
            + "\n"
        )

    @property
    def eval_script(self) -> str:
        self.eval_script_list = self.make_eval_script_list()
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
        repo = self.repo.split("/")[-1].split("__")[-1].split("-")[0]
        # this is the image name created locally
        # once this image created, it will be tagged with repo_image_tag
        return f"commit0.repo.{repo}.{val}:v0".lower()

    @property
    def repo_image_tag(self) -> str:
        """Repo image tag that will be used throughout."""
        repo = self.repo.split("/")[-1]
        tag = f"wentingzhao/{repo}:v0".lower()
        if "__" in repo:  # this is a swebench instance
            repo = repo.split("__")[-1].split("-")[0]
            hash_object = hashlib.sha256()
            hash_object.update(str(self.setup_script).encode("utf-8"))
            hash_value = hash_object.hexdigest()
            val = hash_value[:22]  # 22 characters is still very likely to be unique
            tag = f"wentingzhao/{repo}.{val}:v0".lower()
        return tag

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

    @abstractmethod
    def make_repo_script_list(self) -> list[str]:
        pass

    @abstractmethod
    def make_eval_script_list(self) -> list[str]:
        pass


class Commit0Spec(Spec):
    def make_repo_script_list(self) -> list[str]:
        """Create a list of bash commands to set up the repository for testing.
        This is the setup script for the instance image.
        """
        specs = self.instance["setup"]
        repo = self.instance["repo"]
        env_setup_commit = self.instance["reference_commit"]
        base_commit = self.instance["base_commit"]

        setup_commands = [
            f"git clone -o origin https://github.com/{repo} {self.repo_directory}",
            f"chmod -R 777 {self.repo_directory}",  # So nonroot user can run tests
            f"cd {self.repo_directory}",
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

    def make_eval_script_list(self) -> list[str]:
        """Run the tests."""
        eval_script_list = [
            f"cd {self.repo_directory}",
            "source .venv/bin/activate",
            f"git reset --hard {self.instance['base_commit']}",
            "git apply --allow-empty -v /patch.diff",
            "git status",
            f"{self.instance['test']['test_cmd']} --json-report --json-report-file=report.json --continue-on-collection-errors{{coverage}} {{test_ids}} > test_output.txt 2>&1",
            "echo $? > pytest_exit_code.txt",
        ]
        return eval_script_list


class SimpleSpec(Spec):
    def make_repo_script_list(self) -> list[str]:
        """Create a list of bash commands to set up the repository for testing.
        This is the setup script for the instance image.
        """
        setup_commands = [
            f"mkdir {self.repo_directory} && cd {self.repo_directory}",
            "uv venv --python 3.12",
            "source .venv/bin/activate",
            "uv pip install -U pytest pytest-cov coverage pytest-json-report",
            "which python",
        ]
        return setup_commands

    def make_eval_script_list(self) -> list[str]:
        """Run the tests."""
        eval_script_list = [
            f"cd {self.repo_directory}",
            "source .venv/bin/activate",
            "cat /patch.diff > test.py",
            "pytest test.py > test_output.txt 2>&1",
            "echo $? > pytest_exit_code.txt",
        ]
        return eval_script_list


class SWEBenchSpec(Spec):
    def make_repo_script_list(self) -> list[str]:
        """Create a list of bash commands to set up the repository for testing.
        This is the setup script for the instance image.
        """
        specs = self.instance["setup"]
        repo = self.instance["repo"]
        version = int(str(specs["python"]).split(".")[-1])
        if version < 7:
            specs["python"] = 3.7

        setup_commands = [
            f"git clone -o origin https://github.com/{repo} {self.repo_directory}",
            f"chmod -R 777 {self.repo_directory}",  # So nonroot user can run tests
            f"cd {self.repo_directory}",
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
            if isinstance(specs["packages"], list):
                for package in specs["packages"]:
                    if ".txt" in package:
                        cmd = f"uv pip install -r {package}"
                    else:
                        cmd = f"uv pip install {package}"
                    setup_commands.append(cmd)
            elif isinstance(specs["packages"], str):
                if ".txt" in specs["packages"]:
                    cmd = f"uv pip install -r {specs['packages']}"
                else:
                    cmd = f"uv pip install {specs['packages']}"
                setup_commands.append(cmd)
            else:
                raise TypeError(
                    f"{specs['packages']} has a type other than string and list so couldn't be parsed."
                )

        # Install additional packages if specified
        if "pip_packages" in specs and specs["pip_packages"] is not None:
            pip_packages = [one.split(";")[0].strip() for one in specs["pip_packages"]]
            pip_packages = [f'"{one}"' for one in pip_packages]
            pip_packages = " ".join(pip_packages)
            cmd = f"uv pip install {pip_packages}"
            setup_commands.append(cmd)
        setup_commands.append(
            "uv pip install pytest pytest-cov coverage pytest-json-report"
        )
        return setup_commands

    def make_eval_script_list(self) -> list[str]:
        """Run the tests."""
        specs = self.instance["setup"]
        results = []
        if "install" in specs and specs["install"] is not None:
            installs = specs["install"].split("; ")
            for one in installs:
                if "python -m pip install" in one:
                    install = one.replace("python -m ", "uv run python -m ")
                    install = "uv pip install pip && " + install
                else:
                    install = one
                if install.startswith("pip"):
                    install = "uv " + install
                elif install.startswith("python setup.py"):
                    install = install.replace("python ", "uv run python ")
                results.append(install)
        eval_script_list = (
            [
                f"cd {self.repo_directory}",
                "source .venv/bin/activate",
                f"git reset --hard {self.instance['base_commit']}",
                "git apply --allow-empty -v /patch.diff",
            ]
            + results
            + [
                "git status",
                f"{self.instance['test']['test_cmd']} --json-report --json-report-file=report.json --continue-on-collection-errors{{coverage}} {{test_ids}} > test_output.txt 2>&1",
                "echo $? > pytest_exit_code.txt",
            ]
        )
        return eval_script_list


def get_specs_from_dataset(
    dataset: Union[list[Union[RepoInstance, SimpleInstance]], list[Spec]],
    dataset_type: str,
) -> list[Spec]:
    """Idempotent function that converts a list of RepoInstance objects to a list of Spec objects."""
    if isinstance(dataset[0], Spec):
        return cast(list[Spec], dataset)
    return list(
        map(
            lambda instance: make_spec(instance, dataset_type),
            cast(list["RepoInstance"], dataset),
        )
    )


def make_spec(instance: Union[RepoInstance, SimpleInstance], dataset_type: str) -> Spec:
    if isinstance(instance, Spec):
        return instance
    repo_directory = "/testbed"
    if dataset_type == "commit0":
        return Commit0Spec(
            repo=instance["instance_id"],
            repo_directory=repo_directory,
            instance=instance,
        )
    elif dataset_type == "swebench":
        return SWEBenchSpec(
            repo=instance["instance_id"],
            repo_directory=repo_directory,
            instance=instance,
        )
    elif dataset_type == "simple":
        return SimpleSpec(
            repo="simple",  # all benchmarks with mere function writing will share the simple docker image
            repo_directory=repo_directory,
            instance=instance,
        )
    else:
        raise NotImplementedError(
            f"{dataset_type} is not supported.\nWe only support commit0 and swebench instances for now."
        )


__all__ = []
