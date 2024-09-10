import logging
import os

import docker
import hydra
from datasets import load_dataset
from omegaconf import DictConfig

from typing import Iterator
from commit0.harness.utils import clone_repo
from commit0.harness.constants import REPO_IMAGE_BUILD_DIR, RepoInstance
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="configs", config_name="base")
def main(config: DictConfig) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(hf_name, split="test")  # type: ignore
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

    logger.info("Start building docker images")
    logger.info(f"Please check {REPO_IMAGE_BUILD_DIR} for build details")
    client = docker.from_env()
    build_repo_images(client, specs)
    logger.info("Done building docker images")


__all__ = []
