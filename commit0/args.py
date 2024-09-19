import typer
from pathlib import Path
from typing import List
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


@app.command()
def clone(
    repo_split: str = typer.Argument(
        ...,
        help=f"Split of the repository, one of: {", ".join([highlight(key, Colors.ORANGE) for key in SPLIT.keys()])}",
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory to clone repos"),
) -> None:
    """Commit0 clone a repository."""
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
        ...,
        help=f"Split of the repository, one of {", ".join(highlight(key, Colors.ORANGE) for key in SPLIT.keys())}",
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    num_workers: int = typer.Option(8, help="Number of workers"),
    backend: str = typer.Option("local", help="Backend to use for building"),
) -> None:
    """Commit0 build a repository."""
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
        ...,
        help=f"Name of the repository to get tests for, one of: {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT_ALL)}",
    ),
) -> None:
    """Get tests for a Commit0 repository."""
    if repo_name not in SPLIT_ALL:
        valid_repos = ", ".join([highlight(key, Colors.ORANGE) for key in SPLIT_ALL])
        raise typer.BadParameter(
            f"Invalid {highlight('REPO_NAME', Colors.RED)}. Must be one of: {valid_repos}",
            param_hint="REPO_NAME",
        )

    typer.echo(f"Getting tests for repository: {repo_name}")

    commit0.harness.get_pytest_ids.main(repo_name, stdout=True)


@app.command()
def test(
    repo_or_repo_path: str = typer.Argument(
        ..., help="Directory of the repository to test"
    ),
    branch: str = typer.Argument(..., help="Branch to test"),
    test_ids: str = typer.Argument(..., help="Test IDs to run"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(3600, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
) -> None:
    """Run tests on a Commit0 repository."""
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
        ..., help="Directory of the repository to test"
    ),
    test_ids: str = typer.Argument(..., help="Test IDs to run"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(1800, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
) -> None:
    """Run tests on the reference commit of a Commit0 repository"""
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
        ..., help=f"Split of the repository, one of {SPLIT.keys()}"
    ),
    branch: str = typer.Argument(..., help="Branch to evaluate"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for evaluation"),
    timeout: int = typer.Option(1800, help="Timeout for evaluation in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    num_workers: int = typer.Option(8, help="Number of workers to use"),
) -> None:
    """Evaluate a Commit0 repository."""
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
        ..., help=f"Split of the repository, one of {SPLIT.keys()}"
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
) -> None:
    """Evaluate the reference commit of a Commit0 repository."""
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
        ..., help="Files to lint. If not provided, all files will be linted."
    ),
) -> None:
    """Lint given files if provided, otherwise lint all files in the base directory."""
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
        ..., help=f"Split of the repository, one of {SPLIT.keys()}"
    ),
    owner: str = typer.Argument(..., help="Owner of the repository"),
    branch: str = typer.Argument(..., help="Branch to save"),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    github_token: str = typer.Option(None, help="GitHub token for authentication"),
) -> None:
    """Save a Commit0 repository to GitHub."""
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
