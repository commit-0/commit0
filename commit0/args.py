import typer
from pathlib import Path
from typing import List, Dict, Any
import yaml
import commit0.harness.run_pytest_ids
import commit0.harness.get_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import commit0.harness.evaluate
import commit0.harness.lint
import commit0.harness.save
from commit0.harness.constants import SPLIT, SPLIT_ALL

app = typer.Typer()


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    ORANGE = "\033[95m"


def highlight(text: str, color: str) -> str:
    """Highlight text with a color."""
    return f"{color}{text}{Colors.RESET}"


def read_yaml_config(file_path: str) -> Dict[str, Any]:
    """Read a YAML configuration file."""
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise typer.BadParameter(
            f"Config file not found: {highlight(file_path, Colors.RED)}"
        )
    except yaml.YAMLError as e:
        raise typer.BadParameter(
            f"Invalid YAML in config file: {highlight(str(e), Colors.RED)}"
        )


def validate_config(
    config: Dict[str, Any], required_keys: List[str], type_map: Dict[str, type]
) -> Dict[str, Any]:
    """Validate a configuration."""
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        missing_keys_str = ", ".join(
            highlight(key, Colors.YELLOW) for key in missing_keys
        )
        raise typer.BadParameter(f"Missing required keys in YAML: {missing_keys_str}")

    error_messages = []
    for key, expected_type in type_map.items():
        if key in config:
            value = config[key]
            if not isinstance(value, expected_type):
                error_messages.append(
                    f"  {highlight(key, Colors.RED)}: expected {highlight(expected_type.__name__, Colors.YELLOW)}, got {highlight(type(value).__name__, Colors.RED)}"
                )

    if error_messages:
        error_str = "\n".join(error_messages)
        raise typer.BadParameter(f"Invalid configuration:\n{error_str}")

    return config


def get_validated_config(
    config_name: str, required_keys: List[str], type_map: Dict[str, type]
) -> Dict[str, Any]:
    """Get a validated configuration from a YAML file."""
    typer.echo()  # Add an empty line for better readability
    typer.secho("------------------------", fg=typer.colors.BLUE)
    typer.secho("Configuration File Mode", fg=typer.colors.BLUE, bold=True)
    typer.secho("------------------------", fg=typer.colors.BLUE)
    typer.secho(
        "Using config file. All command-line arguments will be ignored.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        "Values from the YAML file will be used instead.", fg=typer.colors.YELLOW
    )
    typer.echo()  # Add an empty line for better readability

    yaml_config = read_yaml_config(config_name)

    config = validate_config(yaml_config, required_keys, type_map)

    return config


@app.command()
def clone(
    repo_split: str = typer.Argument(
        None,
        help=f"Split of the repository, one of: {", ".join([highlight(key, Colors.ORANGE) for key in SPLIT.keys()])}",
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory to clone repos"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Commit0 clone a repository.

    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file.
    """
    if config_name:
        required_keys = ["repo_split", "dataset_name", "dataset_split", "base_dir"]
        type_map = {
            "repo_split": str,
            "dataset_name": str,
            "dataset_split": str,
            "base_dir": str,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_split = config["repo_split"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        base_dir = config["base_dir"]
    else:
        if repo_split is None:
            raise typer.BadParameter(
                f"Missing argument '{highlight('REPO_SPLIT', Colors.RED)}'.",
                param_hint="REPO_SPLIT",
            )

        if repo_split not in SPLIT:
            valid_splits = ", ".join(
                [highlight(key, Colors.ORANGE) for key in SPLIT.keys()]
            )
            raise typer.BadParameter(
                f"Invalid {highlight('REPO_SPLIT', Colors.RED)}. Must be one of: {valid_splits}",
                param_hint="REPO_SPLIT",
            )

    typer.echo(f"Cloning repository for split: {repo_split}")
    typer.echo(f"Dataset name: {dataset_name}")
    typer.echo(f"Dataset split: {dataset_split}")
    typer.echo(f"Base directory: {base_dir}")

    commit0.harness.setup.main(
        dataset_name,
        dataset_split,
        repo_split,
        base_dir,
    )


@app.command()
def build(
    repo_split: str = typer.Argument(
        None, help=f"Split of the repository, one of {SPLIT.keys()}"
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    num_workers: int = typer.Option(8, help="Number of workers"),
    backend: str = typer.Option("local", help="Backend to use for building"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Commit0 build a repository.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = [
            "repo_split",
            "dataset_name",
            "dataset_split",
            "num_workers",
            "backend",
        ]
        type_map = {
            "repo_split": str,
            "dataset_name": str,
            "dataset_split": str,
            "num_workers": int,
            "backend": str,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_split = config["repo_split"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        num_workers = config["num_workers"]
        backend = config["backend"]
    else:
        if repo_split is None:
            raise typer.BadParameter(
                f"Missing argument '{highlight('REPO_SPLIT', Colors.RED)}'.",
                param_hint="REPO_SPLIT",
            )

        if repo_split not in SPLIT:
            valid_splits = ", ".join(
                [highlight(key, Colors.ORANGE) for key in SPLIT.keys()]
            )
            raise typer.BadParameter(
                f"Invalid {highlight('REPO_SPLIT', Colors.RED)}. Must be one of: {valid_splits}",
                param_hint="REPO_SPLIT",
            )

    typer.echo(f"Building repository for split: {repo_split}")
    typer.echo(f"Dataset name: {dataset_name}")
    typer.echo(f"Dataset split: {dataset_split}")
    typer.echo(f"Number of workers: {num_workers}")
    typer.echo(f"Backend: {backend}")

    commit0.harness.build.main(
        dataset_name,
        dataset_split,
        repo_split,
        num_workers,
        backend,
    )


@app.command()
def get_tests(
    repo_name: str = typer.Argument(
        None,
        help=f"Name of the repository to get tests for, one of: {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT_ALL)}",
    ),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Get tests for a Commit0 repository.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = ["repo_name"]
        type_map = {"repo_name": str}

        config = get_validated_config(config_name, required_keys, type_map)

        repo_name = config["repo_name"]
    else:
        if repo_name is None:
            raise typer.BadParameter(
                f"Missing argument '{highlight('REPO_NAME', Colors.RED)}'.",
                param_hint="REPO_NAME",
            )
        if repo_name not in SPLIT_ALL:
            valid_repos = ", ".join(
                [highlight(key, Colors.ORANGE) for key in SPLIT_ALL]
            )
            raise typer.BadParameter(
                f"Invalid {highlight('REPO_NAME', Colors.RED)}. Must be one of: {valid_repos}",
                param_hint="REPO_NAME",
            )

    typer.echo(f"Getting tests for repository: {repo_name}")

    commit0.harness.get_pytest_ids.main(repo_name, stdout=True)


@app.command()
def test(
    repo_or_repo_path: str = typer.Argument(
        None, help="Directory of the repository to test"
    ),
    branch: str = typer.Argument(None, help="Branch to test"),
    test_ids: str = typer.Argument(None, help="Test IDs to run"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(3600, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Run tests on a Commit0 repository.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = [
            "repo_or_repo_path",
            "branch",
            "test_ids",
            "dataset_name",
            "dataset_split",
            "base_dir",
            "backend",
            "timeout",
            "num_cpus",
        ]
        type_map = {
            "repo_or_repo_path": str,
            "branch": str,
            "test_ids": str,
            "dataset_name": str,
            "dataset_split": str,
            "base_dir": str,
            "backend": str,
            "timeout": int,
            "num_cpus": int,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_or_repo_path = config["repo_or_repo_path"]
        branch = config["branch"]
        test_ids = config["test_ids"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        base_dir = config["base_dir"]
        backend = config["backend"]
        timeout = config["timeout"]
        num_cpus = config["num_cpus"]
    else:
        if repo_or_repo_path is None or branch is None or test_ids is None:
            missing_args = []
            if repo_or_repo_path is None:
                missing_args.append("REPO_OR_REPO_PATH")
            if branch is None:
                missing_args.append("BRANCH")
            if test_ids is None:
                missing_args.append("TEST_IDS")
            missing_args_str = ", ".join(
                [highlight(arg, Colors.RED) for arg in missing_args]
            )
            raise typer.BadParameter(
                f"Missing required argument(s): {missing_args_str}"
            )

    typer.echo(f"Running tests for repository: {repo_or_repo_path}")
    typer.echo(f"Branch: {branch}")
    typer.echo(f"Test IDs: {test_ids}")

    if branch.startswith("branch="):
        branch = branch[len("branch=") :]

    commit0.harness.run_pytest_ids.main(
        dataset_name,
        dataset_split,
        base_dir,
        repo_or_repo_path,
        branch,
        test_ids,
        backend,
        timeout,
        num_cpus,
        stdout=True,
    )


@app.command()
def test_reference(
    repo_or_repo_path: str = typer.Argument(
        None, help="Directory of the repository to test"
    ),
    test_ids: str = typer.Argument(None, help="Test IDs to run"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(1800, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Run tests on the reference commit of a Commit0 repository
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = [
            "repo_or_repo_path",
            "test_ids",
            "dataset_name",
            "dataset_split",
            "base_dir",
            "backend",
            "timeout",
            "num_cpus",
        ]
        type_map = {
            "repo_or_repo_path": str,
            "test_ids": str,
            "dataset_name": str,
            "dataset_split": str,
            "base_dir": str,
            "backend": str,
            "timeout": int,
            "num_cpus": int,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_or_repo_path = config["repo_or_repo_path"]
        test_ids = config["test_ids"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        base_dir = config["base_dir"]
        backend = config["backend"]
        timeout = config["timeout"]
        num_cpus = config["num_cpus"]
    else:
        if repo_or_repo_path is None or test_ids is None:
            missing_args = []
            if repo_or_repo_path is None:
                missing_args.append("REPO_OR_REPO_PATH")
            if test_ids is None:
                missing_args.append("TEST_IDS")
            missing_args_str = ", ".join(
                [highlight(arg, Colors.RED) for arg in missing_args]
            )
            raise typer.BadParameter(
                f"Missing required argument(s): {missing_args_str}"
            )

    typer.echo(f"Running reference tests for repository: {repo_or_repo_path}")
    typer.echo(f"Test IDs: {test_ids}")

    commit0.harness.run_pytest_ids.main(
        dataset_name,
        dataset_split,
        base_dir,
        repo_or_repo_path,
        "reference",
        test_ids,
        backend,
        timeout,
        num_cpus,
        stdout=True,
    )


@app.command()
def evaluate(
    repo_split: str = typer.Argument(
        None, help=f"Split of the repository, one of {SPLIT.keys()}"
    ),
    branch: str = typer.Argument(None, help="Branch to evaluate"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for evaluation"),
    timeout: int = typer.Option(1800, help="Timeout for evaluation in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    num_workers: int = typer.Option(8, help="Number of workers to use"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Evaluate a Commit0 repository.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = [
            "repo_split",
            "branch",
            "dataset_name",
            "dataset_split",
            "base_dir",
            "backend",
            "timeout",
            "num_cpus",
            "num_workers",
        ]
        type_map = {
            "repo_split": str,
            "branch": str,
            "dataset_name": str,
            "dataset_split": str,
            "base_dir": str,
            "backend": str,
            "timeout": int,
            "num_cpus": int,
            "num_workers": int,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_split = config["repo_split"]
        branch = config["branch"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        base_dir = config["base_dir"]
        backend = config["backend"]
        timeout = config["timeout"]
        num_cpus = config["num_cpus"]
        num_workers = config["num_workers"]
    else:
        if repo_split is None or branch is None:  # type: ignore
            missing_args = []
            if repo_split is None:
                missing_args.append("REPO_SPLIT")
            if branch is None:
                missing_args.append("BRANCH")
            missing_args_str = ", ".join(
                [highlight(arg, Colors.RED) for arg in missing_args]
            )
            raise typer.BadParameter(
                f"Missing required argument(s): {missing_args_str}"
            )

        if repo_split not in SPLIT:
            valid_splits = ", ".join(
                [highlight(key, Colors.ORANGE) for key in SPLIT.keys()]
            )
            raise typer.BadParameter(
                f"Invalid repo_split. Must be one of: {valid_splits}",
                param_hint="REPO_SPLIT",
            )

    typer.echo(f"Evaluating repository split: {repo_split}")
    typer.echo(f"Branch: {branch}")

    if branch.startswith("branch="):
        branch = branch[len("branch=") :]

    commit0.harness.evaluate.main(
        dataset_name,
        dataset_split,
        repo_split,
        base_dir,
        branch,
        backend,
        timeout,
        num_cpus,
        num_workers,
    )


@app.command()
def evaluate_reference(
    repo_split: str = typer.Argument(
        None, help=f"Split of the repository, one of {SPLIT.keys()}"
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for evaluation"),
    timeout: int = typer.Option(1800, help="Timeout for evaluation in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    num_workers: int = typer.Option(8, help="Number of workers to use"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Evaluate the reference commit of a Commit0 repository.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = [
            "repo_split",
            "dataset_name",
            "dataset_split",
            "base_dir",
            "backend",
            "timeout",
            "num_cpus",
            "num_workers",
        ]
        type_map = {
            "repo_split": str,
            "dataset_name": str,
            "dataset_split": str,
            "base_dir": str,
            "backend": str,
            "timeout": int,
            "num_cpus": int,
            "num_workers": int,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_split = config["repo_split"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        base_dir = config["base_dir"]
        backend = config["backend"]
        timeout = config["timeout"]
        num_cpus = config["num_cpus"]
        num_workers = config["num_workers"]
    else:
        if repo_split is None:
            raise typer.BadParameter(
                f"Missing required argument: {highlight('REPO_SPLIT', Colors.RED)}"
            )

        if repo_split not in SPLIT:
            valid_splits = ", ".join(
                [highlight(key, Colors.ORANGE) for key in SPLIT.keys()]
            )
            raise typer.BadParameter(
                f"Invalid repo_split. Must be one of: {valid_splits}",
                param_hint="REPO_SPLIT",
            )

    typer.echo(f"Evaluating reference commit for repository split: {repo_split}")

    commit0.harness.evaluate.main(
        dataset_name,
        dataset_split,
        repo_split,
        base_dir,
        "reference",
        backend,
        timeout,
        num_cpus,
        num_workers,
    )


@app.command()
def lint(
    files: List[str] = typer.Argument(
        None, help="Files to lint. If not provided, all files will be linted."
    ),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Lint given files if provided, otherwise lint all files in the base directory.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = ["files"]
        type_map = {"files": list}

        config = get_validated_config(config_name, required_keys, type_map)

        files = config["files"]

    if files:
        for file in files:
            if not Path(file).is_file():
                raise FileNotFoundError(f"File not found: {file}")
        typer.echo(
            f"Linting specific files: {', '.join(highlight(file, Colors.ORANGE) for file in files)}"
        )
    else:
        typer.echo("Linting all files in the repository")

    commit0.harness.lint.main(files)


@app.command()
def save(
    repo_split: str = typer.Argument(
        None, help=f"Split of the repository, one of {SPLIT.keys()}"
    ),
    owner: str = typer.Argument(None, help="Owner of the repository"),
    branch: str = typer.Argument(None, help="Branch to save"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    github_token: str = typer.Option(None, help="GitHub token for authentication"),
    config_name: str = typer.Option(None, help="Path to the YAML configuration file"),
) -> None:
    """Save a Commit0 repository to GitHub.
    
    If --config-name is provided, all other arguments will be ignored and should be specified in the YAML file."""
    if config_name:
        required_keys = [
            "repo_split",
            "owner",
            "branch",
            "dataset_name",
            "dataset_split",
            "base_dir",
            "github_token",
        ]
        type_map = {
            "repo_split": str,
            "owner": str,
            "branch": str,
            "dataset_name": str,
            "dataset_split": str,
            "base_dir": str,
            "github_token": str,
        }

        config = get_validated_config(config_name, required_keys, type_map)

        repo_split = config["repo_split"]
        owner = config["owner"]
        branch = config["branch"]
        dataset_name = config["dataset_name"]
        dataset_split = config["dataset_split"]
        base_dir = config["base_dir"]
        github_token = config["github_token"]
    else:
        if repo_split is None or owner is None or branch is None:
            missing_args = []
            if repo_split is None:
                missing_args.append("REPO_SPLIT")
            if owner is None:
                missing_args.append("OWNER")
            if branch is None:
                missing_args.append("BRANCH")
            missing_args_str = ", ".join(
                [highlight(arg, Colors.RED) for arg in missing_args]
            )
            raise typer.BadParameter(
                f"Missing required argument(s): {missing_args_str}"
            )

        if repo_split not in SPLIT:
            valid_splits = ", ".join(
                [highlight(key, Colors.ORANGE) for key in SPLIT.keys()]
            )
            raise typer.BadParameter(
                f"Invalid repo_split. Must be one of: {valid_splits}",
                param_hint="REPO_SPLIT",
            )

    typer.echo(f"Saving repository split: {repo_split}")
    typer.echo(f"Owner: {owner}")
    typer.echo(f"Branch: {branch}")

    if branch.startswith("branch="):
        branch = branch[len("branch=") :]

    commit0.harness.save.main(
        dataset_name,
        dataset_split,
        repo_split,
        base_dir,
        owner,
        branch,
        github_token,
    )


if __name__ == "__main__":
    app()
