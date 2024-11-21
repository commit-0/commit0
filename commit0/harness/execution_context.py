"""Remote code execution contexts

Implements the interface for local docker containers, remote modal sandboxes,
and HTTP servers.
"""

from abc import ABC, abstractmethod
import docker
import logging
import modal
import modal.io_streams
from enum import StrEnum, auto
from pathlib import Path
import time
from typing import Optional, Type
from types import TracebackType

from commit0.harness.constants import Files
from commit0.harness.spec import Spec
from commit0.harness.docker_build import (
    close_logger,
)
from commit0.harness.docker_utils import (
    cleanup_container,
    create_container,
    copy_from_container,
    copy_to_container,
    exec_run_with_timeout,
)


class ExecutionBackend(StrEnum):
    LOCAL = auto()
    MODAL = auto()


class ExecutionContext(ABC):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        timeout: int,
        num_cpus: int,
        log_dir: Path,
        files_to_copy: Optional[Files] = None,
        files_to_collect: Optional[list[str]] = None,
        rebuild_image: bool = False,
    ):
        """Create the remote execution context

        The execution context can be a Docker container or Modal sandbox.
        The execution context may not persist for the lifetime of this object.
        """
        self.spec = spec
        self.logger = logger
        self.timeout = timeout
        self.num_cpus = num_cpus
        self.log_dir = log_dir
        self.files_to_collect = files_to_collect

    @abstractmethod
    def exec_run_with_timeout(self, command: str) -> tuple[str, bool, float]:
        """Execute a test command"""
        raise NotImplementedError

    def __enter__(self):
        return self

    @abstractmethod
    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        raise NotImplementedError


class Docker(ExecutionContext):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        timeout: int,
        num_cpus: int,
        log_dir: Path,
        files_to_copy: Optional[Files] = None,
        files_to_collect: Optional[list[str]] = None,
        rebuild_image: bool = False,
    ):
        super().__init__(
            spec,
            logger,
            timeout,
            num_cpus,
            log_dir,
            files_to_copy=files_to_copy,
            files_to_collect=files_to_collect,
        )

        self.client = docker.from_env()
        self.container = create_container(
            client=self.client,
            image_name=spec.repo_image_tag,
            container_name=spec.get_container_name(),
            nano_cpus=num_cpus,
            logger=logger,
        )
        self.container.start()
        if files_to_copy:
            for _, f in files_to_copy.items():
                copy_to_container(self.container, f["src"], f["dest"])  # type: ignore

    def exec_run_with_timeout(self, command: str) -> tuple[str, bool, float]:
        """Exec"""
        output = exec_run_with_timeout(self.container, command, self.timeout)

        if self.files_to_collect:
            for fname in self.files_to_collect:
                file = Path(self.spec.repo_directory) / fname
                # Run the test command inside the container to check if the file exists
                exit_code, test_output = self.container.exec_run(
                    f"test -e {file}", demux=True
                )
                # Check the exit code of the command
                if exit_code == 0:
                    copy_from_container(self.container, file, self.log_dir / fname)
        return output

    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        cleanup_container(self.client, self.container, self.logger)
        close_logger(self.logger)


class Modal(ExecutionContext):
    def __init__(
        self,
        spec: Spec,
        logger: logging.Logger,
        timeout: int,
        num_cpus: int,
        log_dir: Path,
        files_to_copy: Optional[Files] = None,
        files_to_collect: Optional[list[str]] = None,
        rebuild_image: bool = False,
    ):
        super().__init__(
            spec,
            logger,
            timeout,
            num_cpus,
            log_dir,
            files_to_copy=files_to_copy,
            files_to_collect=files_to_collect,
        )

        self.app = modal.App.lookup("commit0", create_if_missing=True)

        # the image must exist on dockerhub
        reponame = spec.repo.split("/")[-1]
        image_name = f"wentingzhao/{reponame}:v0".lower()
        image = modal.Image.from_registry(image_name, force_build=rebuild_image)
        if files_to_copy:
            for _, f in files_to_copy.items():
                image = image.copy_local_file(f["src"], f["dest"])  # type: ignore
        self.image = image

    def exec_run_with_timeout(self, command: str) -> tuple[str, bool, float]:
        """Execute command on modal sandbox"""
        start_time = time.time()
        with modal.Volume.ephemeral() as vol:
            if self.files_to_collect:
                command += " && "
                for fname in self.files_to_collect:
                    remote_file = Path(self.spec.repo_directory) / fname
                    cp_cmd = f"test -e {str(remote_file)} && cp {str(remote_file)} /vol/{fname}; "
                    command += cp_cmd
            self.sandbox = modal.Sandbox.create(
                "bash",
                "-c",
                command,
                image=self.image,
                cpu=self.num_cpus,
                timeout=self.timeout,
                app=self.app,
                volumes={"/vol": vol},
            )
            self.sandbox.wait()

            return_code = self.sandbox.returncode
            # https://github.com/modal-labs/modal-client/blob/d577b2916b5c3bf4ebbcb58fadced84d85e1cf8c/modal/sandbox.py#L413
            if return_code == 124:
                timed_out = True
            else:
                timed_out = False

            if self.files_to_collect:
                fnames = vol.listdir("")
                for fname in fnames:
                    fname = fname.path
                    with (self.log_dir / fname).open("wb") as f:
                        for data in vol.read_file(fname):
                            f.write(data)

            self.sandbox.terminate()
            end_time = time.time()
            return self.sandbox.stderr.read(), timed_out, end_time - start_time

    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        close_logger(self.logger)
