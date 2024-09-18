import sys
import os
from abc import ABC, abstractmethod
from pathlib import Path

from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput


class Agents(ABC):
    def __init__(self, max_iteration: int):
        self.max_iteration = max_iteration

    @abstractmethod
    def run(self) -> None:
        """Start agent"""
        raise NotImplementedError


class AiderAgents(Agents):
    def __init__(self, max_iteration: int, model_name: str):
        super().__init__(max_iteration)
        self.model = Model(model_name)

    def run(
        self,
        message: str,
        test_cmd: str,
        lint_cmd: str,
        fnames: list[str],
        log_dir: Path,
    ) -> None:
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
        print(
            f"check {os.path.abspath(chat_history_file)} for prompts and lm generations",
            file=sys.stderr,
        )
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
            lint_cmds=lint_cmd,
            test_cmd=test_cmd,
            io=io,
        )
        coder.max_reflection = self.max_iteration
        coder.stream = False
        coder.run(message)
