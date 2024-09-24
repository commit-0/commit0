import sys
import os
from abc import ABC, abstractmethod
from pathlib import Path
import logging

from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput
from tenacity import retry, wait_exponential, RetryCallState, retry_if_exception_type


class APIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error: {status_code} - {message}")

def handle_logging(logging_name: str, log_file: Path):
    logger = logging.getLogger(logging_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger_handler = logging.FileHandler(log_file)
    logger_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(logger_handler)

class Agents(ABC):
    def __init__(self, max_iteration: int, retry_if_api_error_codes: tuple[int, ...] = (429, 503, 529)):
        self.max_iteration = max_iteration

        # error code 429 is rate limit exceeded for openai and anthropic
        # error code 503 is service overloaded for openai
        # error code 529 is service overloaded for anthropic
        self.retry_if_api_error_codes = retry_if_api_error_codes

    @abstractmethod
    def run(self) -> None:
        """Start agent"""
        raise NotImplementedError


class AiderAgents(Agents):
    def __init__(self, max_iteration: int, model_name: str):
        super().__init__(max_iteration)
        self.model = Model(model_name)

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(APIError)
    )
    def run(
        self,
        message: str,
        test_cmd: str,
        lint_cmd: str,
        fnames: list[str],
        log_dir: Path,
    ) -> None:
        """Start aider agent"""
        try:
            if test_cmd:
                auto_test = True
            else:
                auto_test = False
            if lint_cmd:
                auto_lint = True
            else:
                auto_lint = False
            log_dir = log_dir.resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
            input_history_file = log_dir / ".aider.input.history"
            chat_history_file = log_dir / ".aider.chat.history.md"

            print(
                f"check {os.path.abspath(chat_history_file)} for prompts and lm generations",
                file=sys.stderr,
            )
            # Set up logging
            log_file = log_dir / "aider.log"
            logging.basicConfig(
                filename=log_file,
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

            # Redirect print statements to the log file
            sys.stdout = open(log_file, "a")
            sys.stderr = open(log_file, "a")

            # Configure httpx and backoff logging
            handle_logging("httpx", log_file)
            handle_logging("backoff", log_file)

            io = InputOutput(
                yes=True,
                input_history_file=input_history_file,
                chat_history_file=chat_history_file,
            )
            coder = Coder.create(
                main_model=self.model,
                fnames=fnames,
                auto_lint=auto_lint,
                auto_test=auto_test,
                lint_cmds={"python": lint_cmd},
                test_cmd=test_cmd,
                io=io,
            )
            coder.max_reflection = self.max_iteration
            coder.stream = False

            # Run the agent
            raise Exception("test")
            coder.run(message)
        
        except Exception as e:
            # If the exception is related to API errors, raise an APIError
            if hasattr(e, 'status_code') and e.status_code in self.retry_if_api_error_codes:
                raise APIError(e.status_code, str(e))
            # For other exceptions, re-raise them
            raise
        finally:
            # Close redirected stdout and stderr
            sys.stdout.close()
            sys.stderr.close()
            # Restore original stdout and stderr
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
