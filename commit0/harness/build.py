import argparse
import logging

import docker
from datasets import load_dataset
from typing import Iterator
from commit0.harness.docker_build import build_repo_images
from commit0.harness.spec import make_spec

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    hf_name: str,
    base_dir: str,
    config_file: str,
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(hf_name, split="test")
    specs = []
    for example in dataset:
        spec = make_spec(example)
        specs.append(spec)

    client = docker.from_env()
    build_repo_images(client, specs)
    logger.info("Done building docker images")


def add_init_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hf_name",
        type=str,
        help="HF dataset name",
        default="wentingzhao/commit0_docstring",
    )
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
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    main(
        hf_name=args.hf_name,
        base_dir=args.base_dir,
        config_file=args.config_file,
    )


__all__ = []
