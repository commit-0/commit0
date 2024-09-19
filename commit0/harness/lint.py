import subprocess
import sys
from pathlib import Path


config = """repos:
# Standard hooks
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.3.0
  hooks:
  - id: check-case-conflict
  - id: mixed-line-ending

- repo: https://github.com/astral-sh/ruff-pre-commit
  # Ruff version.
  rev: v0.6.1
  hooks:
    # Run the linter.
    - id: ruff
      args: [ --fix ]
    # Run the formatter.
    - id: ruff-format

- repo: https://github.com/RobertCraigie/pyright-python
  rev: v1.1.376
  hooks:
    - id: pyright"""


def main(base_dir: str, files: list[str]) -> None:
    config_file = Path(".commit0.pre-commit-config.yaml")
    if not config_file.is_file():
        config_file.write_text(config)
    command = ["pre-commit", "run", "--config", config_file, "--files"] + files
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(result.stdout)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Pre-commit checks failed\n{e.output}")
    except FileNotFoundError:
        raise FileNotFoundError("Error: pre-commit command not found. Is it installed?")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")


__all__ = []
