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
    delete_file_from_container,
    exec_run_with_timeout,
)


def read_stream(stream: modal.io_streams.StreamReader) -> str:
    """Read stream"""
    strings = []
    for line in stream:
        strings.append(line)
    return "\n".join(strings)


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

    @abstractmethod
    def exec_run_with_timeout(self, command: str) -> tuple[str, bool, float]:
        """Execute a test command"""
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
    ):
        super().__init__(spec, logger, timeout, num_cpus, log_dir)

        self.client = docker.from_env()
        self.container = create_container(
            client=self.client,
            image_name=spec.repo_image_key,
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

        # copy back report.json if there is any
        report_file = Path(self.spec.repo_directory) / "report.json"
        # Run the test command inside the container to check if the file exists
        exit_code, test_output = self.container.exec_run(
            f"test -e {report_file}", demux=True
        )
        # Check the exit code of the command
        if exit_code == 0:
            copy_from_container(
                self.container, report_file, self.log_dir / "report.json"
            )
            delete_file_from_container(self.container, str(report_file))
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
    ):
        super().__init__(spec, logger, timeout, num_cpus, log_dir)

        self.app = modal.App()

        # the image must exist on dockerhub
        reponame = spec.repo.split("/")[-1]
        image_name = f"wentingzhao/{reponame}:latest"
        image = modal.Image.from_registry(image_name)
        if files_to_copy:
            for _, f in files_to_copy.items():
                image = image.copy_local_file(f["src"], f["dest"])  # type: ignore
        self.image = image

    def exec_run_with_timeout(self, command: str) -> tuple[str, bool, float]:
        """Execute command on modal sandbox"""
        start_time = time.time()
        with modal.Volume.ephemeral() as vol:
            # copy back report.json if there is any
            report_file = Path(self.spec.repo_directory) / "report.json"

            self.sandbox = modal.Sandbox.create(
                "bash",
                "-c",
                f"{command} && cp {str(report_file)} /vol/report.json",
                image=self.image,
                cpu=self.num_cpus,
                timeout=self.timeout,
                app=self.app,
                volumes={"/vol": vol},
            )
            self.sandbox.wait()

            # stdout has been redirected to stderr
            stdout = read_stream(self.sandbox.stderr)

            return_code = self.sandbox.returncode
            # https://github.com/modal-labs/modal-client/blob/d577b2916b5c3bf4ebbcb58fadced84d85e1cf8c/modal/sandbox.py#L413
            if return_code == 124:
                timed_out = True
            else:
                timed_out = False

            # copy over report.json from mount
            with (self.log_dir / "report.json").open("wb") as f:
                for data in vol.read_file("report.json"):
                    f.write(data)

            self.sandbox.terminate()

            end_time = time.time()

            return stdout, timed_out, end_time - start_time

    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        close_logger(self.logger)
