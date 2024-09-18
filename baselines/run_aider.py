import logging
import os
from pathlib import Path
import hydra
from datasets import load_dataset
import traceback
from baselines.baseline_utils import (
    get_message_to_aider,
    get_target_edit_files,
)
from typing import Optional, Type
from types import TracebackType
from hydra.core.config_store import ConfigStore
from baselines.class_types import AiderConfig, Commit0Config
from commit0.harness.constants import SPLIT
from commit0.harness.get_pytest_ids import main as get_tests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from commit0.harness.constants import RUN_AIDER_LOG_DIR
from commit0.harness.docker_build import setup_logger

from aider.coders import Coder
from aider.models import Model

class DirContext:
    def __init__(self, d):
        self.dir = d
        self.cwd = os.getcwd()
    def __enter__(self):
        os.chdir(self.dir)
    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        os.chdir(self.cwd)


def run_aider(
    model_name: str,
    fnames: list[str],
    message: str,
    test_cmd: str,
    lint_cmd: str,
    log_dir: Path,
) -> None:
    if test_cmd:
        auto_test = True
    else:
        auto_test = False
    if lint_cmd:
        auto_lint = True
    else:
        auto_lint = False
    model = Model(model_name)
    input_history_file = log_dir / ".aider.input.history"
    chat_history_file = log_dir / ".aider.chat.history.md"
    io = InputOutput(yes=True, input_history_file=input_history_file, chat_history_file=chat_history_file)
    coder = Coder.create(main_model=model, fnames=fnames, auto_lint=auto_lint, lint_cmds=[lint_cmd], io=io)
    coder.run(message)


def run_aider_for_repo(
    commit0_config: Commit0Config | None,
    aider_config: AiderConfig | None,
    ds: dict,
) -> None:
    """Run Aider for a given repository."""
    # get repo info
    _, repo_name = ds["repo"].split("/")

    repo_name = repo_name.lower()
    repo_name = repo_name.replace(".", "-")

    # Call the commit0 get-tests command to retrieve test files
    test_files_str = get_tests(repo_name, stdout=False)

    test_files = sorted(list(set([i.split(":")[0] for i in test_files_str])))

    repo_path = os.path.join(commit0_config.base_dir, repo_name)
    repo_path = os.path.abspath(repo_path)

    target_edit_files = get_target_edit_files(repo_path)

    with DirContext(repo_path):
        if commit0_config is None or aider_config is None:
            raise ValueError("Invalid input")

        message_to_aider = get_message_to_aider(
            aider_config, target_edit_files, repo_path, ds
        )

        if aider_config.use_lint_info:
            lint_cmd = "pre-commit run --config ../../.pre-commit-config.yaml --files"
        else:
            lint_cmd = ""

        print(
            f"Aider logs for {repo_name} can be found in: {Path.cwd() /RUN_AIDER_LOG_DIR}"
        )

        if aider_config.run_tests:
            for test_file in test_files:
                test_cmd = f"python -m commit0 test {repo_path} {test_file}"
                # set up logging
                test_file_name = test_file.replace(".py", "").replace("/", "__")
                log_dir = RUN_AIDER_LOG_DIR / "with_tests" / test_file_name
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "run_aider.log"
                logger = setup_logger(repo_name, log_file)

                aider_cmd = run_aider(
                    aider_config.llm_name,
                    target_edit_files,
                    message_to_aider,
                    test_cmd,
                    lint_cmd,
                    log_dir,
                )

                # write aider command to log file
                aider_cmd_file = Path(log_dir / "aider_cmd.sh")
                aider_cmd_file.write_text(aider_cmd)

                # write test command to log file
                test_cmd_file = Path(log_dir / "test_cmd.sh")
                test_cmd_file.write_text(test_cmd)

                execute_aider_cmd(aider_cmd, logger)
        else:
            test_cmd = ""
            for f in target_edit_files:
                # set up logging
                file_name = f.replace(".py", "").replace("/", "__")
                log_dir = RUN_AIDER_LOG_DIR / "no_tests" / file_name
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "run_aider.log"
                logger = setup_logger(repo_name, log_file)

                aider_cmd = run_aider(
                    aider_config.llm_name,
                    [f],
                    message_to_aider,
                    test_cmd,
                    lint_cmd,
                    log_dir,
                )
                # write aider command to log file
                aider_cmd_file = Path(log_dir / "aider_cmd.sh")
                aider_cmd_file.write_text(aider_cmd)

                execute_aider_cmd(aider_cmd, logger)


def main() -> None:
    """Main function to run Aider for a given repository.

    Will run in parallel for each repo.
    """
    cs = ConfigStore.instance()
    cs.store(name="user", node=Commit0Config)
    cs.store(name="user", node=AiderConfig)

    hydra.initialize(version_base=None, config_path="configs")
    config = hydra.compose(config_name="aider")

    commit0_config = Commit0Config(**config.commit0_config)
    aider_config = AiderConfig(**config.aider_config)

    if commit0_config is None or aider_config is None:
        raise ValueError("Invalid input")

    dataset = load_dataset(
        commit0_config.dataset_name, split=commit0_config.dataset_split
    )

    filtered_dataset = [
        example
        for example in dataset
        if commit0_config.repo_split == "all"
        or (
            isinstance(example, dict)
            and "repo" in example
            and isinstance(example["repo"], str)
            and example["repo"].split("/")[-1]
            in SPLIT.get(commit0_config.repo_split, [])
        )
    ]

    with tqdm(
        total=len(filtered_dataset), smoothing=0, desc="Running Aider for repos"
    ) as pbar:
        with ThreadPoolExecutor(max_workers=commit0_config.num_workers) as executor:
            # Create a future for running Aider for each repo
            futures = {
                executor.submit(
                    run_aider_for_repo,
                    commit0_config,
                    aider_config,
                    example if isinstance(example, dict) else {},
                ): example
                for example in filtered_dataset
            }
            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    # Update progress bar, check if Aider ran successfully
                    future.result()
                except Exception:
                    traceback.print_exc()
                    continue


if __name__ == "__main__":
    main()
