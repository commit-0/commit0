import logging
import os

from datasets import load_dataset

from typing import Iterator
from commit0.harness.utils import (
    clone_repo,
)
from commit0.harness.constants import BASE_BRANCH, RepoInstance, SPLIT


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    dataset_name: str,
    dataset_split: str,
    repo_split: str,
    base_dir: str,
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    dataset_name = dataset_name.lower()
    if (
        "humaneval" in dataset_name
        or "mbpp" in dataset_name
        or "bigcodebench" in dataset_name
        or "codecontests" in dataset_name
    ):
        return
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        clone_url = f"https://github.com/{example['repo']}.git"
        if "swe" in dataset_name:
            if repo_split != "all" and repo_split not in example["instance_id"]:
                continue
            clone_dir = os.path.abspath(os.path.join(base_dir, example["instance_id"]))
            branch = example["base_commit"]
        else:
            if repo_split != "all" and repo_name not in SPLIT[repo_split]:
                continue
            clone_dir = os.path.abspath(os.path.join(base_dir, repo_name))
            branch = dataset_name.split("/")[-1]
        repo = clone_repo(clone_url, clone_dir, branch, logger)
        if BASE_BRANCH in repo.branches:
            repo.git.branch("-d", BASE_BRANCH)
        repo.git.checkout("-b", BASE_BRANCH)
        logger.info(f"Checked out the base branch: {BASE_BRANCH}")


__all__ = []
