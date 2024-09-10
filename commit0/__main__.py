import argparse
import commit0.harness.run_pytest_ids
import commit0.harness.build
import commit0.harness.setup


def main() -> None:
    parser = argparse.ArgumentParser(description="Commit0 version control system")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    commit0.harness.setup.add_init_args(subparsers.add_parser("clone"))
    commit0.harness.build.add_init_args(subparsers.add_parser("build"))
    commit0.harness.run_pytest_ids.add_init_args(subparsers.add_parser("test"))

    args = parser.parse_args()

    if args.command == "clone":
        commit0.harness.setup.run(args)
    elif args.command == "build":
        commit0.harness.build.run(args)
    elif args.command == "test":
        commit0.harness.run_pytest_ids.run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

__all__ = []
