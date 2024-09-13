""" Remote code execution contexts

Implements the interface for local docker containers, remote modal sandboxes,
and HTTP servers.
"""


from abc import ABC
import docker
import logging
import os
import modal
from pathlib import Path

from commit0.harness.spec import Spec
from commit0.harness.docker_build import (
    close_logger,
    setup_logger,
)
from commit0.harness.docker_utils import (
    cleanup_container,
    create_container,
    copy_from_container,
    copy_to_container,
    copy_ssh_pubkey_from_container,
    delete_file_from_container,
    exec_run_with_timeout,
)
from commit0.harness.utils import (
    EvaluationError,
    extract_test_output,
    get_hash_string,
    get_ip,
    get_user,
)


class ExecutionContext(ABC):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        eval_file: Path,
        timeout: int,
        log_dir: Path,
    ):
        """ Create the remote execution context

        The execution context will persist for the lifetime of this object.
        The execution context can be a Docker container or Modal sandbox.
        """
        raise NotImplementedError

    def copy_ssh_pubkey_from_remote(self):
        raise NotImplementedError

    def copy_to_remote(self, local_path, remote_path):
        raise NotImplementedError

    def exec_run_with_timeout(self, command, timeout):
        raise NotImplementedError

    def exec_run(self, command):
        raise NotImplementedError

    def copy_from_remote(self, remote_path, local_path):
        raise NotImplementedError

    def delete_file_from_remote(self, remote_path):
        raise NotImplementedError

    def __enter__(self):
        raise NotImplementedError

    def __exit__(self, exc_type, exc_value, exc_traceback):
        raise NotImplementedError


class Docker(ExecutionContext):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        eval_file: Path,
        timeout: int,
        log_dir: Path,
    ):
        client = docker.from_env()
        self.logger = logger
        self.container = create_container(
            client=client,
            image_name=spec.repo_image_key,
            container_name=spec.get_container_name(),
            logger=logger,
        )
        self.container.start()
        self.copy_ssh_pubkey_from_remote()

    def copy_ssh_pubkey_from_remote(self) -> None:
        copy_ssh_pubkey_from_container(self.container)

    def copy_to_remote(self, local_file: Path, remote_path: Path) -> None:
        copy_to_container(self.container, local_file, remote_path)

    def exec_run_with_timeout(self, command: str, timeout: int) -> ():
        return exec_run_with_timeout(
            self.container, command, timeout
        )

    def exec_run(self, command: str) -> None:
        return self.container.exec_run(command, demux=True)

    def copy_from_remote(self, remote_path: Path, local_path: Path) -> None:
        copy_from_container(self.container, remote_path, local_path)

    def delete_file_from_remote(self, remote_path: Path) -> None:
        delete_file_from_container(self.container, str(remote_path))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        cleanup_container(self.client, self.container, self.logger)
        close_logger(self.logger)


class Modal(ExecutionContext):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        eval_file: Path,
        timeout: int,
        log_dir: Path,
    ):
        self.logger = logger
        # the image must exist on dockerhub
        reponame = spec.repo.split("/")[-1]
        image_name = f"wentingzhao/{reponame}"
        image = modal.Image.from_registry(image_name)

        self.nfs = modal.NetworkFileSystem.ephemeral().__enter__()
        self.sandbox = modal.Sandbox.create(
            "sleep",
            "infinity",
            image=image,
            network_file_systems={
                "/vol": self.nfs,
            },
        )

        self.copy_ssh_pubkey_from_remote()

    def copy_ssh_pubkey_from_remote(self):
        process = self.sandbox.exec("bash", "-c", "cat /root/.ssh/id_rsa.pub")
        public_key = "".join([line for line in process.stdout]).strip()

        # add to authorized keys locally. copy-pasted from utils
        local_authorized_keys_path = os.path.expanduser("~/.ssh/authorized_keys")
        os.makedirs(os.path.dirname(local_authorized_keys_path), exist_ok=True)
        if not os.path.exists(local_authorized_keys_path):
            # Since the file does not exist, create it
            open(local_authorized_keys_path, "a").close()
            write = True
        else:
            with open(local_authorized_keys_path, "r") as authorized_keys_file:
                content = authorized_keys_file.read()
                if public_key not in content:
                    write = True
                else:
                    write = False
        if write:
            with open(local_authorized_keys_path, "a") as authorized_keys_file:
                authorized_keys_file.write(public_key + "\n")

    def copy_to_remote(self, local_path: Path, remote_path: Path) -> None:
        with local_path.open("rb") as f:
            self.nfs.write_file(str(local_path), f)
        self.sandbox.exec("bash", "-c", f"cp /vol/{str(local_path)} {str(remote_path)}")

    def exec_run_with_timeout(self, command: str, timeout: int) -> None:
        """Execute command on modal sandbox"""
        process = self.sandbox.exec("bash", "-c", command)
        stdout = []
        for line in process.stdout:
            stdout.append(line)
        stderr = []
        for line in process.stderr:
            stderr.append(line)
        return "\n".join(stdout), False, 1
        return "\n".join(stdout), "\n".join(stderr)

    def exec_run(self, command: str) -> None:
        """Execute command on modal sandbox"""
        process = self.sandbox.exec("bash", "-c", command)
        stdout = []
        for line in process.stdout:
            stdout.append(line)
        stderr = []
        for line in process.stderr:
            stderr.append(line)
        return 1, "\n".join(stdout)

    def copy_from_remote(self, remote_path: Path, local_path: Path) -> None:
        """Copy file from modal sandbox"""
        process = self.sandbox.exec("bash", "-c", f"cat {str(remote_path)}")
        output = "".join([line for line in process.stdout]).strip()
        with local_path.open("w") as f:
            f.write(output)

    def delete_file_from_remote(src, remote_path):
        self.sandbox.exec("bash", "-c", f"rm {str(remote_path)}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.nfs.__exit__()
