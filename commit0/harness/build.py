import logging

import docker
from datasets import load_dataset
from typing import Iterator

from omegaconf import DictConfig
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec
from commit0.harness.constants import RepoInstance
import hydra

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="configs", config_name="base")
def main(config: DictConfig) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(hf_name, split="test")  # type: ignore
    specs = []
    for example in dataset:
        spec = make_spec(example)
        specs.append(spec)

    client = docker.from_env()
    build_repo_images(client, specs)
    logger.info("Done building docker images")


__all__ = []
