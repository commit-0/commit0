import logging
import os

import docker
from datasets import load_dataset

from typing import Iterator
from commit0.harness.utils import clone_repo
from commit0.harness.constants import REPO_IMAGE_BUILD_DIR, RepoInstance
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(dataset_name: str, dataset_split: str, base_dir: str) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    out = dict()
    specs = []
    for example in dataset:
        spec = make_spec(example)
        specs.append(spec)
        repo_name = example["repo"].split("/")[-1]
        out[repo_name] = example
        out[repo_name]["local_path"] = os.path.abspath(
            os.path.join(base_dir, repo_name)
        )
        clone_url = f"https://github.com/{example['repo']}.git"
        clone_repo(
            clone_url, out[repo_name]["local_path"], example["base_commit"], logger
        )
        break


__all__ = []
