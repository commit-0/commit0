import argparse
import logging
import os

import docker
import yaml
from datasets import load_dataset

from commit0.collect.utils import clone_repo
from commit0.harness.constants import REPO_IMAGE_BUILD_DIR
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(hf_name: str, base_dir: str, config_file: str) -> None:
    dataset = load_dataset(hf_name, split="test")
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
        clone_repo(clone_url, out[repo_name]["local_path"], example["base_commit"])

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
    args = parser.parse_args()
    main(**vars(args))
