import commit0.harness.run_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import copy
import sys
import hydra
from hydra.core.config_store import ConfigStore
from commit0.configs.config_class import Commit0Config


def main() -> None:
    command = sys.argv[1]
    # type check config values
    cs = ConfigStore.instance()
    cs.store(name="base", node=Commit0Config)
    # have hydra to ignore all command-line arguments
    sys_argv = copy.deepcopy(sys.argv)
    sys.argv = [sys.argv[0]]
    hydra.initialize(version_base=None, config_path="configs")
    config = hydra.compose(config_name="base")
    # after hydra gets all configs, put command-line arguments back
    sys.argv = sys_argv

    if command == "clone":
        commit0.harness.setup.main(
            config.dataset_name, config.dataset_split, config.base_dir
        )
    elif command == "build":
        commit0.harness.build.main(
            config.dataset_name, config.dataset_split, config.num_workers
        )
    elif command == "test":
        repo = sys.argv[2]
        test_ids = sys.argv[3]
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
