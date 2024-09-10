import argparse
import logging
import os

import docker
import yaml
from datasets import load_dataset

from commit0.harness.utils import clone_repo, create_branch
from commit0.harness.constants import REPO_IMAGE_BUILD_DIR
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(hf_name: str, base_dir: str, config_file: str, backend: str, repo: str) -> None:
    dataset = load_dataset(hf_name, split="test")
    out = dict()
    out["backend"] = backend
    out["base_repo_dir"] = base_dir
    out["repos"] = dict()
    specs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo != "all" and repo_name != repo:
            logger.info(f"Skipping {repo_name}")
            continue
        spec = make_spec(example)
        specs.append(spec)
        out["repos"][repo_name] = example
        clone_url = f"https://github.com/{example['repo']}.git"
        clone_dir = os.path.join(out["base_repo_dir"], repo_name)
        repo = clone_repo(clone_url, clone_dir, example["base_commit"], logger)
        create_branch(repo, "aider", logger)

    config_file = os.path.abspath(config_file)
    with open(config_file, "w") as f:
        yaml.dump(out, f, default_flow_style=False)
    logger.info(f"Config file has been written to {config_file}")
    logger.info("Start building docker images")
    logger.info(f"Please check {REPO_IMAGE_BUILD_DIR} for build details")
    client = docker.from_env()
    build_repo_images(client, specs)
    logger.info("Done building docker images")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf_name", type=str, help="HF dataset name")
    parser.add_argument(
        "--base_dir",
        type=str,
        default="repos/",
        help="base directory to write repos to",
    )
    parser.add_argument(
        "--config_file",
        type=str,
        default="config.yml",
        help="where to write config file to",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["local", "modal"],
        default="modal",
        help="specify evaluation backend to be local or modal (remote)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="all",
        help="which repos to setup. all or one from dataset",
    )
    args = parser.parse_args()
    main(**vars(args))
