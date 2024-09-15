import json
import logging
import os
import traceback

from datasets import load_dataset

from typing import Iterator
from commit0.harness.utils import (
    add_key,
    add_safe_directory,
    setup_user,
    setup_ssh_directory,
)
from commit0.harness.constants import RepoInstance, SPLIT
from commit0.harness.spec import make_spec


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(dataset_name: str, dataset_split: str, repo_split: str, base_dir: str, git_user: str, key_path: str) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    setup_user(git_user, logger)
    setup_ssh_directory(git_user, logger)
    with open(key_path, 'r') as f:
        public_keys = json.load(f)

    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        spec = make_spec(example)
        local_dir = os.path.abspath(os.path.join(base_dir, repo_name))
        add_safe_directory(local_dir, logger)
        add_key(git_user, public_keys[spec.repo_image_key])
        logger.info(f"Added public key from {spec.repo_image_key}")


__all__ = []
