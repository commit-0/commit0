import commit0.harness.run_pytest_ids
import commit0.harness.get_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import commit0.harness.evaluate
import commit0.harness.save
import copy
import sys
import os
import hydra
from hydra.core.config_store import ConfigStore
from commit0.configs.config_class import Commit0Config
from commit0.harness.constants import COMMANDS, SPLIT


def main() -> None:
    command = sys.argv[1]
    if command not in COMMANDS:
        raise ValueError(
            f"command must be from {', '.join(COMMANDS)}, but you provided {command}"
        )
    # type check config values
    cs = ConfigStore.instance()
    cs.store(name="user", group="Commit0Config", node=Commit0Config)
    # have hydra to ignore all command-line arguments
    sys_argv = copy.deepcopy(sys.argv)
    sys.argv = [sys.argv[0]]
    hydra.initialize(version_base=None, config_path="configs")
    config = hydra.compose(config_name="user")
    # after hydra gets all configs, put command-line arguments back
    sys.argv = sys_argv
    # repo_split: split from command line has a higher priority than split in hydra
    if command in [
        "clone",
        "build",
        "evaluate",
        "evaluate-reference",
        "save",
    ]:
        if len(sys.argv) >= 3:
            if sys.argv[2] not in SPLIT:
                raise ValueError(
                    f"repo split must be from {', '.join(SPLIT.keys())}, but you provided {sys.argv[2]}"
                )
            config.repo_split = sys.argv[2]
    config.base_dir = os.path.abspath(config.base_dir)

    if command == "clone":
        commit0.harness.setup.main(
            config.dataset_name,
            config.dataset_split,
            config.repo_split,
            config.base_dir,
            config.branch,
        )
    elif command == "build":
        commit0.harness.build.main(
            config.dataset_name,
            config.dataset_split,
            config.repo_split,
            config.num_workers,
            config.backend,
            config.key_path,
        )
    elif command == "get-tests":
        repo = sys.argv[2]
        commit0.harness.get_pytest_ids.main(repo, stdout=True)
    elif command == "test" or command == "test-reference":
        repo = sys.argv[2]
        test_ids = sys.argv[3]
        if command == "test-reference":
            config.branch = "reference"
        commit0.harness.run_pytest_ids.main(
            config.dataset_name,
            config.dataset_split,
            config.base_dir,
            repo,
            config.branch,
            test_ids,
            config.backend,
            config.timeout,
            stdout=True,
        )
    elif command == "evaluate" or command == "evaluate-reference":
        if command == "evaluate-reference":
            config.branch = "reference"
        commit0.harness.evaluate.main(
            config.dataset_name,
            config.dataset_split,
            config.repo_split,
            config.base_dir,
            config.branch,
            config.backend,
            config.timeout,
            config.num_workers,
        )
    elif command == "save":
        organization = sys.argv[3]
        commit0.harness.save.main(
            config.dataset_name,
            config.dataset_split,
            config.repo_split,
            config.base_dir,
            organization,
            config.branch,
            config.github_token,
        )


if __name__ == "__main__":
    main()

__all__ = []
