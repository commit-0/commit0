#!/usr/bin/env python3

import argparse
import logging
import os
from typing import Optional

from datasets import load_dataset, Dataset

from utils import (
    Repo,
    run_pytest
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(dataset_name: str, token: Optional[str] = None):
    """
    Main thread for creating task instances from existing repositories

    Args:
        repo_file (str): path to repository YAML file
        organization (str): under which organization to fork repos to
        token (str): GitHub token
    """
    if token is None:
        # Get GitHub token from environment variable if not provided
        token = os.environ.get("GITHUB_TOKEN")

    dataset = load_dataset(dataset_name, split="test")
    out = []
    for idx, one in enumerate(dataset):
        owner, repo = one["repo"].split("/")
        repo = Repo(
            owner,
            repo,
            organization=owner,
            head=one["environment_setup_commit"],
            setup=one["environment_setup_commands"],
            token=token
        )
        results = run_pytest(repo, "run", one["test_path"])
        out.append({"name": one["repo"], "report": results})
        new_ds = Dataset.from_list(out)
        new_ds.to_json("report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_name", type=str, help="HF dataset name")
    parser.add_argument("--token", type=str, help="GitHub token")
    args = parser.parse_args()
    main(**vars(args))
