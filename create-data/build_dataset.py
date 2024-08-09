#!/usr/bin/env python3

import argparse
import json
import logging
import os
from typing import Optional

from utils import (
    generate_base_commit,
    extract_patches,
    Repo,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_instance(repo: Repo, commit: str) -> dict:
    """
    Create a single task instance from a pull request, where task instance is:

    {
        repo (str): owner/repo this task instance is from,
        base_commit (str): SHA of the base commit for starter repo,
        environment_setup_commit(str): SHA of the commit for setting up environment,
        patch (str): reference solution as .patch (apply to base commit),
        test_patch (str): test suite as .patch (apply to base commit),
    }
    """
    #base_commit= generate_base_commit(repo, commit)
    base_commit = ""
    #patch, test_patch = extract_patches(repo, base_commit)
    patch, test_patch = "", ""
    #created_at = repo.commit(base_commit.committed_datetime)
    created_at = ""
    return {
        "repo": repo.repo.full_name,
        "instance_id": (repo.repo.full_name + "-01").replace(
            "/", "__"
        ),
        "base_commit": base_commit,
        "environment_setup_commit": commit,
        "patch": patch,
        "test_patch": test_patch,
        "problem_statement": "",
        "hints_text": "",
        "created_at": created_at,
    }


def main(repo_file: str, output: str, token: Optional[str] = None):
    """
    Main thread for creating task instances from existing repositories

    Args:
        pr_file (str): path to pull request JSONL file
        output (str): output file name
        token (str): GitHub token
    """
    if token is None:
        # Get GitHub token from environment variable if not provided
        token = os.environ.get("GITHUB_TOKEN")

    def load_repo(repo_name):
        # Return repo object for a given repo name
        owner, repo = repo_name.split("/")
        return Repo(owner, repo, token=token)

    # todo: fork
    with open(output, 'w') as output:
        for ix, line in enumerate(open(repo_file)):
            info = json.loads(line)
            repo = load_repo(info['name'])
            commit = info['commit']
            # Construct instance fields
            instance_id = (
                info['name'] + "-01"
            )
            instance_id = instance_id.replace("/", "__")
            # Create task instance
            instance = create_instance(repo, commit)
            print(
                json.dumps(instance), end="\n", flush=True, file=output
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_file", type=str, help="Path to pull request JSONL file")
    parser.add_argument("output", type=str, help="Output file name")
    parser.add_argument("--token", type=str, help="GitHub token")
    args = parser.parse_args()
    main(**vars(args))
