import logging
import os
import subprocess
from functools import partial
from pathlib import Path

import hydra
from datasets import load_dataset
from omegaconf import OmegaConf
from tqdm.contrib.concurrent import thread_map

from baselines.baseline_utils import (
    PROMPT_HEADER,
    REFERENCE_HEADER,
    REPO_INFO_HEADER,
    UNIT_TESTS_INFO_HEADER,
    find_files_with_error,
    get_dir_info,
    get_prompt,
    get_reference,
)
from baselines.class_types import AiderConfig, BaselineConfig, Commit0Config

# from aider.run_aider import get_aider_cmd

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_aider_cmd(
    model: str,
    files: str,
    message_to_aider: str,
    test_cmd: str,
) -> str:
    """Get the Aider command based on the given context."""
    aider_cmd = f"aider --model {model} --file {files} --message \"{message_to_aider}\" --auto-test --test --test-cmd '{test_cmd}' --yes"

    return aider_cmd


def run_aider_for_repo(
    commit0_config: Commit0Config | None,
    aider_config: AiderConfig | None,
    ds: dict,
) -> None:
    """Run Aider for a given repository."""
    if commit0_config is None or aider_config is None:
        raise ValueError("Invalid input")

    # get repo info
    _, repo_name = ds["repo"].split("/")

    # TODO: assuming we have all test_files, which we currently do not have
    test_files = ds["test_files"]

    repo_path = os.path.join(commit0_config.base_dir, repo_name)
    target_edit_files = find_files_with_error(repo_path)

    target_edit_files_cmd_args = " ".join(target_edit_files)

    # support context for aider
    prompt = f"{PROMPT_HEADER} " + get_prompt(target_edit_files_cmd_args)

    if aider_config.use_unit_tests_info and ds["test"]["test_dir"]:
        unit_tests_info = f"\n{UNIT_TESTS_INFO_HEADER} " + get_dir_info(
            dir_path=Path(os.path.join(repo_path, ds["test"]["test_dir"])),
            prefix="",
            include_stubs=True,
        )
    else:
        unit_tests_info = ""

    # TODO: assuming we have specification, which we currently do not have
    if aider_config.use_reference_info and ds["specification"]:
        reference = f"\n{REFERENCE_HEADER} " + get_reference(ds["specification"])
    else:
        reference = ""

    if aider_config.use_repo_info:
        repo_info = f"\n{REPO_INFO_HEADER} " + get_dir_info(
            dir_path=Path(repo_path), prefix="", max_depth=2, include_stubs=False
        )
    else:
        repo_info = ""

    message_to_aider = prompt + reference + repo_info + unit_tests_info

    for test_file in test_files:
        test_cmd = f"python -m commit0.harness.run_pytest_ids --repo {repo_name} --test_ids {test_file} --branch_name aider"

        aider_cmd = get_aider_cmd(
            aider_config.llm_name,
            target_edit_files_cmd_args,
            message_to_aider,
            test_cmd,
        )

        try:
            result = subprocess.call(aider_cmd, shell=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with exit code {e.returncode}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")

        except OSError as e:
            if e.errno == 63:  # File name too long error
                logger.error("Command failed due to file name being too long")
                logger.error(f"Command: {''.join(aider_cmd)}")
            else:
                logger.error(f"OSError occurred: {e}")
        if result != 0:
            logger.error(f"Aider command failed with exit code {result}")
            logger.error(f"Aider command: {aider_cmd}")


@hydra.main(version_base=None, config_path="config", config_name="aider")
def main(config: BaselineConfig) -> None:
    """Main function to run Aider for a given repository.

    Will run in parallel for each repo.
    """
    config = BaselineConfig(config=OmegaConf.to_object(config))
    commit0_config = config.commit0_config
    aider_config = config.aider_config

    dataset = load_dataset(commit0_config.dataset_name, split="test")

    thread_map(
        partial(run_aider_for_repo, commit0_config, aider_config),
        dataset,
        desc="Running aider for repos",
        max_workers=10,
    )


if __name__ == "__main__":
    main()
