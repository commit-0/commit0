import json
import logging
import traceback

import docker
from datasets import load_dataset
from tqdm import tqdm
from typing import Iterator

from commit0.harness.constants import RepoInstance, SPLIT
from commit0.harness.docker_build import build_repo_images
from commit0.harness.execution_context import (
    ExecutionBackend,
    Docker,
    Modal,
)
from commit0.harness.spec import make_spec

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    dataset_name: str, dataset_split: str, repo_split: str, num_workers: int, backend: str, key_path: str
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    specs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        spec = make_spec(example)
        specs.append(spec)

    if ExecutionBackend(backend) == ExecutionBackend.MODAL:
        execution_context = Modal
    elif ExecutionBackend(backend) == ExecutionBackend.LOCAL:
        client = docker.from_env()
        build_repo_images(client, specs, num_workers)
        execution_context = Docker

    # get ssh key from each docker image
    img2key = dict()
    for spec in tqdm(specs, desc="Retrieving public keys from docker images"):
        try:
            with execution_context(spec, logger, timeout=60) as context:
                key = context.get_ssh_pubkey_from_remote(user="root")
                img2key[spec.repo_image_key] = key
        except Exception as e:
            error_msg = (
                f"General error: {e}\n"
                f"{traceback.format_exc()}\n"
            )
            raise RuntimeError(error_msg)
    with open(key_path, 'w') as json_file:
        json.dump(img2key, json_file, indent=4)


__all__ = []
