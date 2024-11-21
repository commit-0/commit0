import typer
from pathlib import Path
from typing import Union, List
from typing_extensions import Annotated
import commit0.harness.run_pytest_ids
import commit0.harness.get_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import commit0.harness.evaluate
import commit0.harness.lint
import commit0.harness.save
from commit0.harness.constants import SPLIT, SPLIT_ALL
from commit0.harness.utils import get_active_branch
import subprocess
import yaml
import os
import sys

commit0_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="""
    Commit-0 is a real-world AI coding challenge. Can your agent generate a working library from commit 0?

    See the website at https://commit-0.github.io/ for documentation and more information about Commit-0.
    """,
)


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    ORANGE = "\033[95m"


def check_commit0_path() -> None:
    """Code adapted from https://github.com/modal-labs/modal-client/blob/a8ddd418f8c65b7e168a9125451eeb70da2b6203/modal/cli/entry_point.py#L55

    Checks whether the `commit0` executable is on the path and usable.
    """
    url = "https://commit-0.github.io/setup/"
    try:
        subprocess.run(["commit0", "--help"], capture_output=True)
        # TODO(erikbern): check returncode?
        return
    except FileNotFoundError:
        typer.echo(
            typer.style(
                "The `commit0` command was not found on your path!", fg=typer.colors.RED
            )
            + "\n"
            + typer.style(
                "You may need to add it to your path or use `python -m commit0` as a workaround.",
                fg=typer.colors.RED,
            )
        )
    except PermissionError:
        typer.echo(
            typer.style("The `commit0` command is not executable!", fg=typer.colors.RED)
            + "\n"
            + typer.style(
                "You may need to give it permissions or use `python -m commit0` as a workaround.",
                fg=typer.colors.RED,
            )
        )
    typer.echo(f"See more information here:\n\n{url}")
    typer.echo("─" * 80)  # Simple rule to separate content


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


def write_commit0_config_file(dot_file_path: str, config: dict) -> None:
    with open(dot_file_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def read_commit0_config_file(dot_file_path: str) -> dict:
    # Check if the file exists before attempting to read it
    if not os.path.exists(dot_file_path):
        raise FileNotFoundError(
            f"The commit0 dot file '{dot_file_path}' does not exist."
        )
    with open(dot_file_path, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


@commit0_app.command()
def setup(
    repo_split: str = typer.Argument(
        ...,
        help=f"Split of repositories, one of: {', '.join([highlight(key, Colors.ORANGE) for key in SPLIT.keys()])}",
    ),
    dataset_name: str = typer.Option(
        "wentingzhao/commit0_combined", help="Name of the Huggingface dataset"
    ),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory to clone repos to"),
    commit0_config_file: str = typer.Option(
        ".commit0.yaml", help="Storing path for stateful commit0 configs"
    ),
) -> None:
    """Commit0 clone a repo split."""
    check_commit0_path()
    check_valid(repo_split, SPLIT)

    base_dir = str(Path(base_dir).resolve())

    typer.echo(f"Cloning repository for split: {highlight(repo_split, Colors.ORANGE)}")
    typer.echo(f"Dataset name: {highlight(dataset_name, Colors.ORANGE)}")
    typer.echo(f"Dataset split: {highlight(dataset_split, Colors.ORANGE)}")
    typer.echo(f"Base directory: {highlight(base_dir, Colors.ORANGE)}")
    typer.echo(
        f"Commit0 dot file path: {highlight(commit0_config_file, Colors.ORANGE)}"
    )

    commit0.harness.setup.main(
        dataset_name,
        dataset_split,
        repo_split,
        base_dir,
    )

    # after successfully setup, write the commit0 dot file
    write_commit0_config_file(
        commit0_config_file,
        {
            "dataset_name": dataset_name,
            "dataset_split": dataset_split,
            "repo_split": repo_split,
            "base_dir": base_dir,
        },
    )


@commit0_app.command()
def build(
    num_workers: int = typer.Option(8, help="Number of workers"),
    commit0_config_file: str = typer.Option(
        ".commit0.yaml",
        help="Path to the commit0 dot file, where the setup config is stored",
    ),
    verbose: int = typer.Option(
        1,
        "--verbose",
        "-v",
        help="Set this to 2 for more logging information",
        count=True,
    ),
) -> None:
    """Build Commit0 split you choose in Setup Stage."""
    check_commit0_path()

    commit0_config = read_commit0_config_file(commit0_config_file)
    check_valid(commit0_config["repo_split"], SPLIT)

    typer.echo(
        f"Building repository for split: {highlight(commit0_config['repo_split'], Colors.ORANGE)}"
    )
    typer.echo(
        f"Dataset name: {highlight(commit0_config['dataset_name'], Colors.ORANGE)}"
    )
    typer.echo(
        f"Dataset split: {highlight(commit0_config['dataset_split'], Colors.ORANGE)}"
    )
    typer.echo(f"Number of workers: {highlight(str(num_workers), Colors.ORANGE)}")

    commit0.harness.build.main(
        commit0_config["dataset_name"],
        commit0_config["dataset_split"],
        commit0_config["repo_split"],
        num_workers,
        verbose,
    )


@commit0_app.command()
def get_tests(
    repo_name: str = typer.Argument(
        ...,
        help=f"Name of the repository to get tests for, one of: {', '.join(highlight(key, Colors.ORANGE) for key in SPLIT_ALL)}",
    ),
) -> None:
    """Get tests for a Commit0 repository."""
    check_commit0_path()
    check_valid(repo_name, SPLIT_ALL)

    commit0.harness.get_pytest_ids.main(repo_name, verbose=1)


@commit0_app.command()
def test(
    repo_or_repo_path: str = typer.Argument(
        ..., help="Directory of the repository to test"
    ),
    test_ids: str = typer.Argument(
        None,
        help='All ways pytest supports to run and select tests. Please provide a single string. Example: "test_mod.py", "testing/", "test_mod.py::test_func", "-k \'MyClass and not method\'"',
    ),
    branch: Union[str, None] = typer.Option(
        None, help="Branch to test (branch MUST be provided or use --reference)"
    ),
    backend: str = typer.Option("modal", help="Backend to use for testing"),
    timeout: int = typer.Option(1800, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    reference: Annotated[
        bool, typer.Option("--reference", help="Test the reference commit")
    ] = False,
    coverage: Annotated[
        bool, typer.Option("--coverage", help="Whether to get coverage information")
    ] = False,
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Whether to rebuild an image"
    ),
    commit0_config_file: str = typer.Option(
        ".commit0.yaml",
        help="Path to the commit0 dot file, where the setup config is stored",
    ),
    verbose: int = typer.Option(
        1,
        "--verbose",
        "-v",
        help="Set this to 2 for more logging information",
        count=True,
    ),
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read test names from stdin. Example: `echo 'test_mod.py' | commit0 test REPO --branch BRANCH`",
    ),
) -> None:
    """Run tests on a Commit0 repository."""
    check_commit0_path()
    if repo_or_repo_path.endswith("/"):
        repo_or_repo_path = repo_or_repo_path[:-1]
    check_valid(repo_or_repo_path.split("/")[-1], SPLIT_ALL)

    commit0_config = read_commit0_config_file(commit0_config_file)

    if reference:
        branch = "reference"
    if branch is None and not reference:
        git_path = os.path.join(
            commit0_config["base_dir"], repo_or_repo_path.split("/")[-1]
        )
        branch = get_active_branch(git_path)

    if stdin:
        # Read test names from stdin
        test_ids = sys.stdin.read().strip()
    elif test_ids is None:
        typer.echo("Error: test_ids must be provided or use --stdin option", err=True)
        raise typer.Exit(code=1)

    if verbose == 2:
        typer.echo(f"Running tests for repository: {repo_or_repo_path}")
        typer.echo(f"Branch: {branch}")
        typer.echo(f"Test IDs: {test_ids}")

    commit0.harness.run_pytest_ids.main(
        commit0_config["dataset_name"],
        commit0_config["dataset_split"],
        commit0_config["base_dir"],
        repo_or_repo_path,
        branch,  # type: ignore
        test_ids,
        coverage,
        backend,
        timeout,
        num_cpus,
        rebuild,
        verbose,
    )


@commit0_app.command()
def evaluate(
    branch: Union[str, None] = typer.Option(
        None, help="Branch to evaluate (branch MUST be provided or use --reference)"
    ),
    backend: str = typer.Option("modal", help="Backend to use for evaluation"),
    timeout: int = typer.Option(1800, help="Timeout for evaluation in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    num_workers: int = typer.Option(8, help="Number of workers to use"),
    reference: Annotated[
        bool, typer.Option("--reference", help="Evaluate the reference commit.")
    ] = False,
    coverage: Annotated[
        bool, typer.Option("--coverage", help="Whether to get coverage information")
    ] = False,
    commit0_config_file: str = typer.Option(
        ".commit0.yaml",
        help="Path to the commit0 dot file, where the setup config is stored",
    ),
    rebuild: bool = typer.Option(False, "--rebuild", help="Whether to rebuild images"),
) -> None:
    """Evaluate Commit0 split you choose in Setup Stage."""
    check_commit0_path()
    if reference:
        branch = "reference"

    commit0_config = read_commit0_config_file(commit0_config_file)
    check_valid(commit0_config["repo_split"], SPLIT)

    typer.echo(f"Evaluating repository split: {commit0_config['repo_split']}")
    typer.echo(f"Branch: {branch}")

    commit0.harness.evaluate.main(
        commit0_config["dataset_name"],
        commit0_config["dataset_split"],
        commit0_config["repo_split"],
        commit0_config["base_dir"],
        branch,
        coverage,
        backend,
        timeout,
        num_cpus,
        num_workers,
        rebuild,
    )


@commit0_app.command()
def lint(
    repo_or_repo_dir: str = typer.Argument(
        ..., help="Directory of the repository to test"
    ),
    files: Union[List[Path], None] = typer.Option(
        None, help="Files to lint. If not provided, all files will be linted."
    ),
    commit0_config_file: str = typer.Option(
        ".commit0.yaml",
        help="Path to the commit0 dot file, where the setup config is stored",
    ),
    verbose: int = typer.Option(
        1,
        "--verbose",
        "-v",
        help="Set this to 2 for more logging information",
        count=True,
    ),
) -> None:
    """Lint given files if provided, otherwise lint all files in the base directory."""
    check_commit0_path()
    commit0_config = read_commit0_config_file(commit0_config_file)
    appended_files = None
    if files is not None:
        appended_files = []
        for path in files:
            path = Path(commit0_config["base_dir"]) / Path(repo_or_repo_dir) / path
            if not path.is_file():
                raise FileNotFoundError(f"File not found: {str(path)}")
            appended_files.append(path)
    if verbose == 2:
        typer.echo(f"Linting repo: {highlight(str(repo_or_repo_dir), Colors.ORANGE)}")
    commit0.harness.lint.main(
        commit0_config["dataset_name"],
        commit0_config["dataset_split"],
        repo_or_repo_dir,
        appended_files,
        commit0_config["base_dir"],
    )


@commit0_app.command()
def save(
    owner: str = typer.Argument(..., help="Owner of the repository"),
    branch: str = typer.Argument(..., help="Branch to save"),
    github_token: str = typer.Option(None, help="GitHub token for authentication"),
    commit0_config_file: str = typer.Option(
        ".commit0.yaml",
        help="Path to the commit0 dot file, where the setup config is stored",
    ),
) -> None:
    """Save Commit0 split you choose in Setup Stage to GitHub."""
    check_commit0_path()
    commit0_config = read_commit0_config_file(commit0_config_file)
    check_valid(commit0_config["repo_split"], SPLIT)

    typer.echo(f"Saving repository split: {commit0_config['repo_split']}")
    typer.echo(f"Owner: {owner}")
    typer.echo(f"Branch: {branch}")

    commit0.harness.save.main(
        commit0_config["dataset_name"],
        commit0_config["dataset_split"],
        commit0_config["repo_split"],
        commit0_config["base_dir"],
        owner,
        branch,
        github_token,
    )


__all__ = []
