import logging
import os
import subprocess
from functools import partial

import hydra
from datasets import load_dataset
from omegaconf import OmegaConf
from tqdm.contrib.concurrent import thread_map
import tarfile
from baselines.baseline_utils import (
    get_message_to_aider,
    get_target_edit_files_cmd_args,
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

    repo_name = repo_name.lower()
    repo_name = repo_name.replace(".", "-")
    with tarfile.open(f"commit0/data/test_ids/{repo_name}.tar.bz2", "r:bz2") as tar:
        for member in tar.getmembers():
            if member.isfile():
                file = tar.extractfile(member)
                if file:
                    test_files_str = file.read().decode("utf-8")
                    # print(content.decode("utf-8"))

    test_files = test_files_str.split("\n") if isinstance(test_files_str, str) else []
    test_files = sorted(list(set([i.split(":")[0] for i in test_files])))

    repo_path = os.path.join(commit0_config.base_dir, repo_name)

    target_edit_files_cmd_args = get_target_edit_files_cmd_args(repo_path)

    message_to_aider = get_message_to_aider(
        aider_config, target_edit_files_cmd_args, repo_path, ds
    )

    for test_file in test_files:
        test_cmd = f"python -m commit0.harness.run_pytest_ids --repo {repo_name} --test_ids {test_file} --branch_name aider"

        aider_cmd = get_aider_cmd(
            aider_config.llm_name,
            target_edit_files_cmd_args,
            message_to_aider,
            test_cmd,
        )

        try:
            _ = subprocess.call(aider_cmd, shell=True)
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


@hydra.main(version_base=None, config_path="config", config_name="aider")
def main(config: BaselineConfig) -> None:
    """Main function to run Aider for a given repository.

    Will run in parallel for each repo.
    """
    config = BaselineConfig(config=OmegaConf.to_object(config))
    commit0_config = config.commit0_config
    aider_config = config.aider_config

    if commit0_config is None or aider_config is None:
        raise ValueError("Invalid input")

    dataset = load_dataset(commit0_config.dataset_name, split="test")

    thread_map(
        partial(run_aider_for_repo, commit0_config, aider_config),
        dataset,
        desc="Running aider for repos",
        max_workers=10,
    )


if __name__ == "__main__":
    main()
