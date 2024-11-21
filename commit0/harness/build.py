import logging

import docker
from datasets import load_dataset
from typing import Iterator

from commit0.harness.constants import RepoInstance, SPLIT
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    dataset_name: str,
    dataset_split: str,
    repo_split: str,
    num_workers: int,
    verbose: int,
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    specs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        spec = make_spec(example)
        specs.append(spec)

    client = docker.from_env()
    build_repo_images(client, specs, num_workers, verbose)


__all__ = []
