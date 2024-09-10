#!/usr/bin/env python3

import argparse
import logging
import os
import yaml
from typing import Optional

from datasets import Dataset, DatasetDict

from commit0.collect.utils import (
    generate_base_commit,
    Repo,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_instance(
    repo: Repo, base_branch_name: str, removal: str, raw_info: dict
) -> dict:
    """Create a single task instance from a commit, where task instance is:

    {
        repo (Repo): owner/repo this task instance is from,
        base_commit (str): SHA of the base commit for starter repo,
        reference_commit(str): SHA of the commit for setting up environment,
        patch (str): reference solution as .patch (apply to base commit),
    }
    """
    # extract_test_names needs to be called on the environment set up commit
    base_commit = generate_base_commit(
        repo,
        spec_url=raw_info["specification"],
        base_branch_name=base_branch_name,
        removal=removal,
    )
    setup = dict()
    setup["python"] = raw_info["python"]
    setup["install"] = raw_info["install"]
    setup["specification"] = raw_info["specification"]
    if "pre_install" in raw_info:
        setup["pre_install"] = raw_info["pre_install"]
    if "packages" in raw_info:
        setup["packages"] = raw_info["packages"]
    if "pip_packages" in raw_info:
        setup["pip_packages"] = raw_info["pip_packages"]
    return {
        "repo": f"{repo.owner}/{repo.name}",
        "base_commit": base_commit,
        "reference_commit": repo.commit,
        "setup": setup,
        "test": {"test_cmd": raw_info["test_cmd"], "test_dir": raw_info["test_dir"]},
    }


def main(
    repo_file: str,
    hf_name: str,
    organization: str,
    base_branch_name: str,
    removal: str,
    token: Optional[str] = None,
) -> None:
    """Main thread for creating task instances from existing repositories

    Args:
    ----
        repo_file (str): path to repository YAML file
        hf_name (str): where to upload the dataset
        organization (str): under which organization to fork repos to
        base_branch_name (str): base of the branch name under which the base commit will be sent to
        removal (str): strategy to remove code body
        token (str): GitHub token

    """
    if token is None:
        # Get GitHub token from environment variable if not provided
        token = os.environ.get("GITHUB_TOKEN")

    examples = []
    with open(repo_file, "r") as f:
        repo_file = yaml.safe_load(f)
    for idx, info in repo_file.items():
        logger.info(f"Working on {info['name']}")
        # can only provide tag or commit
        assert (info["tag"] is None) ^ (info["commit"] is None)
        if info["tag"] is not None:
            if not info["tag"].startswith("tags/"):
                info["tag"] = "tags/" + info["tag"]
            head = info["tag"]
        else:
            head = info["commit"]
        owner, repo = info["name"].split("/")
        repo = Repo(owner, repo, organization=organization, head=head, token=token)
        # Create task instance
        instance = create_instance(repo, base_branch_name, removal, info)
        examples.append(instance)
    ds = Dataset.from_list(examples)
    ds = DatasetDict({"test": ds})
    hf_name = f"{hf_name}_{removal}"
    ds.push_to_hub(hf_name, private=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_file", type=str, help="Path to pull request YAML file")
    parser.add_argument("--hf_name", type=str, help="HF dataset name")
    parser.add_argument(
        "--organization",
        type=str,
        default="commit-0",
        help="under which organization to fork repos to",
    )
    parser.add_argument("--token", type=str, help="GitHub token")
    parser.add_argument(
        "--base_branch_name",
        type=str,
        default="commit0",
        help="base of the branch name under which the base commit will be sent to",
    )
    parser.add_argument("--removal", type=str, default="all", help="Removal method")
    args = parser.parse_args()
    main(**vars(args))
