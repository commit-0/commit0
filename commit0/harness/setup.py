import logging
import os

import docker
import yaml
from datasets import load_dataset

from omegaconf import DictConfig, OmegaConf
import hydra

from commit0.harness.utils import clone_repo, create_branch
from commit0.harness.constants import REPO_IMAGE_BUILD_DIR
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="configs", config_name="base")
def main(config: DictConfig) -> None:
    OmegaConf.to_yaml(config)
    dataset = load_dataset(config.dataset_name, split="test")
    out = dict()
    out["backend"] = config.backend
    out["base_repo_dir"] = config.base_dir
    specs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if config.build != "all" and repo_name != repo:
            logger.info(f"Skipping {repo_name}")
            continue
        spec = make_spec(example)
        specs.append(spec)
        clone_url = f"https://github.com/{example['repo']}.git"
        clone_dir = os.path.join(out["base_repo_dir"], repo_name)
        repo = clone_repo(clone_url, clone_dir, example["base_commit"], logger)
        create_branch(repo, config.branch, logger)

    logger.info("Start building docker images")
    logger.info(f"Please check {REPO_IMAGE_BUILD_DIR} for build details")
    client = docker.from_env()
    build_repo_images(client, specs)
    logger.info("Done building docker images")

if __name__ == '__main__':
    main()
