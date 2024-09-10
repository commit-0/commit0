import argparse
import commit0.harness.run_pytest_ids
import commit0.harness.build
import commit0.harness.setup


def main() -> None:
    parser = argparse.ArgumentParser(description="Commit0 version control system")
    parser.add_subparsers(dest="command", help="Available commands")

    args = parser.parse_args()

    if args.command == "clone":
        commit0.harness.setup.main()
    elif args.command == "build":
        commit0.harness.build.main()
    elif args.command == "test":
        commit0.harness.run_pytest_ids.main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

__all__ = []
