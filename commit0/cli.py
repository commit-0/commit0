import typer
from pathlib import Path
from typing import List, Union
from typing_extensions import Annotated
import commit0.harness.run_pytest_ids
import commit0.harness.get_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import commit0.harness.evaluate
import commit0.harness.lint
import commit0.harness.save
from commit0.harness.constants import SPLIT, SPLIT_ALL

app = typer.Typer(add_completion=False)


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    ORANGE = "\033[95m"


def highlight(text: str, color: str) -> str:
    """Highlight text with a color."""
    return f"{color}{text}{Colors.RESET}"


def check_valid(one: str, total: Union[list[str], dict[str, list[str]]]) -> None:
    if isinstance(total, dict):
        total = list(total.keys())
    if one not in total:
        valid = ", ".join([highlight(key, Colors.ORANGE) for key in total])
        raise typer.BadParameter(
            f"Invalid {highlight('REPO_OR_REPO_SPLIT', Colors.RED)}. Must be one of: {valid}",
            param_hint="REPO or REPO_SPLIT",
        )


@app.command()
def setup(
    repo_split: str = typer.Argument(
        ...,
        help=f"Split of repositories, one of: {', '.join([highlight(key, Colors.ORANGE) for key in SPLIT.keys()])}",
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory to clone repos to"),
) -> None:
    """Commit0 clone a repo split."""
    check_valid(repo_split, SPLIT)

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
        help=f"Split of repositories, one of {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT.keys())}",
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    num_workers: int = typer.Option(8, help="Number of workers"),
) -> None:
    """Commit0 build a repository."""
    check_valid(repo_split, SPLIT)

    typer.echo(f"Building repository for split: {repo_split}")
    typer.echo(f"Dataset name: {dataset_name}")
    typer.echo(f"Dataset split: {dataset_split}")
    typer.echo(f"Number of workers: {num_workers}")

    commit0.harness.build.main(
        dataset_name,
        dataset_split,
        repo_split,
        num_workers,
    )


@app.command()
def get_tests(
    repo_name: str = typer.Argument(
        ...,
        help=f"Name of the repository to get tests for, one of: {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT_ALL)}",
    ),
) -> None:
    """Get tests for a Commit0 repository."""
    check_valid(repo_name, SPLIT_ALL)

    typer.echo(f"Getting tests for repository: {repo_name}")

    commit0.harness.get_pytest_ids.main(repo_name, stdout=True)


@app.command()
def test(
    repo_or_repo_path: str = typer.Argument(
        ..., help="Directory of the repository to test"
    ),
    test_ids: str = typer.Argument(
        ...,
        help='All ways pytest supports to run and select tests. Please provide a single string. Example: "test_mod.py", "testing/", "test_mod.py::test_func", "-k \'MyClass and not method\'"',
    ),
    branch: Union[str, None] = typer.Option(
        None, help="Branch to test (branch MUST be provided or use --reference)"
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(1800, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    reference: Annotated[
        bool, typer.Option("--reference", help="Test the reference commit.")
    ] = False,
) -> None:
    """Run tests on a Commit0 repository."""
    if repo_or_repo_path.endswith("/"):
        repo_or_repo_path = repo_or_repo_path[:-1]
    check_valid(repo_or_repo_path.split("/")[-1], SPLIT_ALL)
    if not branch and not reference:
        raise typer.BadParameter(
            f"Invalid {highlight('BRANCH', Colors.RED)}. Either --reference or provide a branch name.",
            param_hint="BRANCH",
        )
    if reference:
        branch = "reference"
    assert branch is not None, "branch is not specified"

    typer.echo(f"Running tests for repository: {repo_or_repo_path}")
    typer.echo(f"Branch: {branch}")
    typer.echo(f"Test IDs: {test_ids}")

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
def evaluate(
    repo_split: str = typer.Argument(
        ...,
        help=f"Split of repositories, one of {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT.keys())}",
    ),
    branch: Union[str, None] = typer.Option(
        None, help="Branch to evaluate (branch MUST be provided or use --reference)"
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
    reference: Annotated[
        bool, typer.Option("--reference", help="Evaluate the reference commit.")
    ] = False,
) -> None:
    """Evaluate a Commit0 repository."""
    if not branch and not reference:
        raise typer.BadParameter(
            f"Invalid {highlight('BRANCH', Colors.RED)}. Either --reference or provide a branch name",
            param_hint="BRANCH",
        )
    if reference:
        branch = "reference"
    assert branch is not None, "branch is not specified"

    check_valid(repo_split, SPLIT)

    typer.echo(f"Evaluating repository split: {repo_split}")
    typer.echo(f"Branch: {branch}")

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
def lint(
    files: List[Path] = typer.Argument(
        ..., help="Files to lint. If not provided, all files will be linted."
    ),
) -> None:
    """Lint given files if provided, otherwise lint all files in the base directory."""
    assert len(files) > 0, "No files to lint."
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {str(path)}")
    typer.echo(
        f"Linting specific files: {', '.join(highlight(str(file), Colors.ORANGE) for file in files)}"
    )
    commit0.harness.lint.main(files)


@app.command()
def save(
    repo_split: str = typer.Argument(
        ...,
        help=f"Split of the repository, one of {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT.keys())}",
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
    check_valid(repo_split, SPLIT)

    typer.echo(f"Saving repository split: {repo_split}")
    typer.echo(f"Owner: {owner}")
    typer.echo(f"Branch: {branch}")

    commit0.harness.save.main(
        dataset_name,
        dataset_split,
        repo_split,
        base_dir,
        owner,
        branch,
        github_token,
    )


__all__ = []
