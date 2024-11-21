import sys
from abc import ABC, abstractmethod
from pathlib import Path
import logging

from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput
import re
import os


def handle_logging(logging_name: str, log_file: Path) -> None:
    """Handle logging for agent"""
    logger = logging.getLogger(logging_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger_handler = logging.FileHandler(log_file)
    logger_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(logger_handler)


class AgentReturn(ABC):
    def __init__(self, log_file: Path):
        self.log_file = log_file

        self.last_cost = 0.0


class Agents(ABC):
    def __init__(self, max_iteration: int):
        self.max_iteration = max_iteration

    @abstractmethod
    def run(self) -> AgentReturn:
        """Start agent"""
        raise NotImplementedError


class AiderReturn(AgentReturn):
    def __init__(self, log_file: Path):
        super().__init__(log_file)
        self.last_cost = self.get_money_cost()

    def get_money_cost(self) -> float:
        """Get accumulated money cost from log file"""
        last_cost = 0.0
        with open(self.log_file, "r") as file:
            for line in file:
                if "Tokens:" in line and "Cost:" in line:
                    match = re.search(
                        r"Cost: \$\d+\.\d+ message, \$(\d+\.\d+) session", line
                    )
                    if match:
                        last_cost = float(match.group(1))
        return last_cost


class AiderAgents(Agents):
    def __init__(self, max_iteration: int, model_name: str):
        super().__init__(max_iteration)
        self.model = Model(model_name)
        # Check if API key is set for the model
        if "gpt" in model_name:
            api_key = os.environ.get("OPENAI_API_KEY", None)
        elif "claude" in model_name:
            api_key = os.environ.get("ANTHROPIC_API_KEY", None)
        elif "gemini" in model_name:
            api_key = os.environ.get("API_KEY", None)
        else:
            raise ValueError(f"Unsupported model: {model_name}")

        if not api_key:
            raise ValueError(
                "API Key Error: There is no API key associated with the model for this agent. "
                "Edit model_name parameter in .agent.yaml, export API key for that model, and try again."
            )

    def run(
        self,
        message: str,
        test_cmd: str,
        lint_cmd: str,
        fnames: list[str],
        log_dir: Path,
        test_first: bool = False,
        lint_first: bool = False,
    ) -> AgentReturn:
        """Start aider agent"""
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
        coder.max_reflections = self.max_iteration
        coder.stream = True

        # Run the agent
        if test_first:
            test_errors = coder.commands.cmd_test(test_cmd)
            if test_errors:
                coder.run(test_errors)
        elif lint_first:
            coder.commands.cmd_lint(fnames=fnames)
        else:
            coder.run(message)

        # Close redirected stdout and stderr
        sys.stdout.close()
        sys.stderr.close()
        # Restore original stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        return AiderReturn(log_file)
