import commit0.harness.run_pytest_ids
import commit0.harness.build
import commit0.harness.setup
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
    cs.store(name="user", node=Commit0Config)
    # have hydra to ignore all command-line arguments
    sys_argv = copy.deepcopy(sys.argv)
    sys.argv = [sys.argv[0]]
    hydra.initialize(version_base=None, config_path="configs")
    config = hydra.compose(config_name="user")
    # after hydra gets all configs, put command-line arguments back
    sys.argv = sys_argv
    # repo_split: split from command line has a higher priority than split in hydra
    if command in ["clone", "build"]:
        if len(sys.argv) == 3:
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
        )
    elif command == "build":
        commit0.harness.build.main(
            config.dataset_name,
            config.dataset_split,
            config.repo_split,
            config.num_workers,
        )
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
        )


if __name__ == "__main__":
    main()

__all__ = []