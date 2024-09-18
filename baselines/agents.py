from abc import ABC, abstractmethod
from pathlib import Path

from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput

class Agents(ABC):
    @abstractmethod
    def run(self):
        raise NotImplementedError

class AiderAgents(Agents):
    def __init__(self, model_name: str):
        self.model = Model(model_name)

    def run(self, message: str, test_cmd: str, lint_cmd: str, fnames: list[str], log_dir: Path) -> None:
        if test_cmd:
            auto_test = True
        else:
            auto_test = False
        if lint_cmd:
            auto_lint = True
        else:
            auto_lint = False
        log_dir.mkdir(parents=True, exist_ok=True)
        input_history_file = log_dir / ".aider.input.history"
        chat_history_file = log_dir / ".aider.chat.history.md"
        io = InputOutput(yes=True, input_history_file=input_history_file, chat_history_file=chat_history_file)
        coder = Coder.create(main_model=self.model, fnames=fnames, auto_lint=auto_lint, lint_cmds=lint_cmd, io=io)
        coder.run(message)
