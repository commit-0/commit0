import os
import sys


def serialize_files(directory) -> None:
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            splitted = file_path.split("/")
            hidden = False
            for one in splitted:
                if one.startswith("."):
                    hidden = True
                    break
            if hidden:
                continue
            try:
                with open(file_path, "r") as f:
                    print(f"[start of {os.path.relpath(file_path, directory)}]")
                    for i, line in enumerate(f, start=1):
                        print(f"{i} {line}", end="")
                    print(f"\n[end of {os.path.relpath(file_path, directory)}]")
            except Exception as e:
                print(f"Could not read file {file_path}: {e}")


if __name__ == "__main__":
    repo_path = sys.argv[1]
    serialize_files(repo_path)
