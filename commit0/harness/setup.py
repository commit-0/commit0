import logging
import os

from datasets import load_dataset

from typing import Iterator
from commit0.harness.utils import clone_repo, create_branch
from commit0.harness.constants import RepoInstance, SPLIT


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    dataset_name: str, dataset_split: str, repo_split: str, base_dir: str, branch: str
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        clone_url = f"https://github.com/{example['repo']}.git"
        clone_dir = os.path.abspath(os.path.join(base_dir, repo_name))
        local_repo = clone_repo(clone_url, clone_dir, example["base_commit"], logger)
        create_branch(local_repo, branch, logger)


__all__ = []
