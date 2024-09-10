import commit0.harness.run_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import sys


def main() -> None:
    command = sys.argv[1]

    if command == "clone":
        commit0.harness.setup.main()
    elif command == "build":
        commit0.harness.build.main()
    elif command == "test":
        commit0.harness.run_pytest_ids.main()


if __name__ == "__main__":
    main()

__all__ = []
