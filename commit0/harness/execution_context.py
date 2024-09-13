"""Remote code execution contexts

Implements the interface for local docker containers, remote modal sandboxes,
and HTTP servers.
"""

from abc import ABC, abstractmethod
import docker
import logging
import os
import modal
from pathlib import Path
from typing import Optional, Type
from types import TracebackType

from commit0.harness.spec import Spec
from commit0.harness.utils import (
    EvaluationError,
)
from commit0.harness.docker_build import (
    close_logger,
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


def read_stream(stream: modal.io_streams.StreamReader) -> str:
    """Read stream"""
    strings = []
    for line in stream:
        strings.append(line)
    return "\n".join(strings)


class ExecutionContext(ABC):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        eval_file: Path,
        timeout: int,
        log_dir: Path,
    ):
        """Create the remote execution context

        The execution context will persist for the lifetime of this object.
        The execution context can be a Docker container or Modal sandbox.
        """
        self.spec = spec
        self.logger = logger
        self.eval_file = eval_file
        self.timeout = timeout
        self.log_dir = log_dir

    @abstractmethod
    def copy_ssh_pubkey_from_remote(self) -> None:
        """Copy"""
        raise NotImplementedError

    @abstractmethod
    def copy_to_remote(self, local_path: Path, remote_path: Path) -> None:
        """Copy"""
        raise NotImplementedError

    @abstractmethod
    def exec_run_with_timeout(self, command: str, timeout: int) -> None:
        """Exec"""
        raise NotImplementedError

    @abstractmethod
    def exec_run(self, command: str) -> None:
        """Exec"""
        raise NotImplementedError

    @abstractmethod
    def copy_from_remote(self, remote_path: Path, local_path: Path) -> None:
        """Copy"""
        raise NotImplementedError

    @abstractmethod
    def delete_file_from_remote(self, remote_path: Path) -> None:
        """Delete"""
        raise NotImplementedError

    def write_test_output(self, test_output: str, timed_out: bool) -> None:
        """Write test output"""
        test_output_path = self.log_dir / "test_output.txt"
        with open(test_output_path, "w") as f:
            f.write(test_output)
            if timed_out:
                f.write(f"\n\nTimeout error: {self.timeout} seconds exceeded.")
                raise EvaluationError(
                    self.spec.repo,
                    f"Test timed out after {self.timeout} seconds.",
                    self.logger,
                )

        # copy back report.json if there is any
        report_file = Path(self.spec.repo_directory) / "report.json"
        # Run the test command inside the container to check if the file exists
        exit_code, output = self.exec_run(f"test -e {report_file}")
        # Check the exit code of the command
        if exit_code == 0:
            self.copy_from_remote(report_file, self.log_dir / "report.json")
            self.delete_file_from_remote(str(report_file))

    def __enter__(self):
        return self

    @abstractmethod
    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> bool:
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
        super().__init__(spec, logger, eval_file, timeout, log_dir)

        self.client = docker.from_env()
        self.container = create_container(
            client=self.client,
            image_name=spec.repo_image_key,
            container_name=spec.get_container_name(),
            logger=logger,
        )
        self.container.start()
        self.copy_ssh_pubkey_from_remote()
        copy_to_container(self.container, eval_file, Path("/eval.sh"))

    def copy_ssh_pubkey_from_remote(self) -> None:
        """Copy"""
        copy_ssh_pubkey_from_container(self.container)

    def copy_to_remote(self, local_file: Path, remote_path: Path) -> None:
        """Copy"""
        copy_to_container(self.container, local_file, remote_path)

    def exec_run_with_timeout(self, command: str, timeout: int) -> ():
        """Exec"""
        return exec_run_with_timeout(self.container, command, timeout)

    def exec_run(self, command: str) -> None:
        """Exec"""
        return self.container.exec_run(command, demux=True)

    def copy_from_remote(self, remote_path: Path, local_path: Path) -> None:
        """Copy"""
        copy_from_container(self.container, remote_path, local_path)

    def delete_file_from_remote(self, remote_path: Path) -> None:
        """Delete"""
        delete_file_from_container(self.container, str(remote_path))

    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> bool:
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
        super().__init_(spec, logger, eval_file, timeout, log_dir)

        # the image must exist on dockerhub
        reponame = spec.repo.split("/")[-1]
        image_name = f"wentingzhao/{reponame}"
        image = modal.Image.from_registry(image_name).copy_local_file(
            eval_file, "/eval.sh"
        )

        self.sandbox = modal.Sandbox.create(
            "sleep",
            "infinity",
            image=image,
            cpu=4.0,
            timeout=timeout,
        )

        self.copy_ssh_pubkey_from_remote()

    def copy_ssh_pubkey_from_remote(self) -> None:
        """Copy ssh pubkey"""
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
        """Copy"""
        tempname = "tmpfile"
        with local_path.open("rb") as f:
            self.nfs.write_file(tempname, f)
        self.sandbox.exec("bash", "-c", f"cp /vol/{tempname} {str(remote_path)}")

    def exec_run_with_timeout(self, command: str, timeout: int) -> None:
        """Execute command on modal sandbox"""
        print("Executing:", command)
        process = self.sandbox.exec("bash", "-c", command)
        print("stdout")
        stdout = read_stream(process.stdout)
        print("stderr")
        stderr = read_stream(process.stderr)
        print(stderr)
        return stdout, False, 1
        return stdout, stderr

    def exec_run(self, command: str) -> None:
        """Execute command on modal sandbox"""
        process = self.sandbox.exec("bash", "-c", command)
        stdout = read_stream(process.stdout)
        stderr = read_stream(process.stderr)
        print(stderr)
        return 1, stdout

    def copy_from_remote(self, remote_path: Path, local_path: Path) -> None:
        """Copy file from modal sandbox"""
        process = self.sandbox.exec("bash", "-c", f"cat {str(remote_path)}")
        output = "".join([line for line in process.stdout]).strip()
        with local_path.open("w") as f:
            f.write(output)

    def delete_file_from_remote(self, remote_path: Path) -> None:
        """Delete"""
        self.sandbox.exec("bash", "-c", f"rm {str(remote_path)}")

    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> bool:
        self.sandbox.terminate()
        close_logger(self.logger)
