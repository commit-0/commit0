import typer
from pathlib import Path
from typing import List, Dict, Any
import yaml
from enum import Enum
import commit0.harness.run_pytest_ids
import commit0.harness.get_pytest_ids
import commit0.harness.build
import commit0.harness.setup
import commit0.harness.evaluate
import commit0.harness.lint
import commit0.harness.save
from commit0.harness.constants import SPLIT_ALL, SPLIT_MINITORCH, SPLIT_SIMPY, SPLIT_LITE
app = typer.Typer()

class AllRepos(str, Enum):
    STATS_MODELS = "statsmodels"
    PYTHON_PROGRESSBAR = "python-progressbar"
    XARRAY = "xarray"
    IMBALANCED_LEARN = "imbalanced-learn"
    WEB3_PY = "web3.py"
    SCRAPY = "scrapy"
    SEABORN = "seaborn"
    PYPDF = "pypdf"
    PEXPECT = "pexpect"
    PYTEST = "pytest"
    PYLINT = "pylint"
    JOBLIB = "joblib"
    DULWICH = "dulwich"
    VIRTUALENV = "virtualenv"
    MINITORCH = "minitorch"
    NETWORKX = "networkx"
    REQUESTS = "requests"
    SPHINX = "sphinx"
    JEDI = "jedi"
    MOVIEPY = "moviepy"
    LOGURU = "loguru"
    PARAMIKO = "paramiko"
    GEOPANDAS = "geopandas"
    BITSTRING = "bitstring"
    FASTAPI = "fastapi"
    CHARDET = "chardet"
    TORNADO = "tornado"
    PYTHON_PROMPT_TOOLKIT = "python-prompt-toolkit"
    ATTRS = "attrs"
    PYBOY = "PyBoy"
    PYDANTIC = "pydantic"
    FILESYSTEM_SPEC = "filesystem_spec"
    TLSLITE_NG = "tlslite-ng"
    GRAPHENE = "graphene"
    MIMESIS = "mimesis"
    BABEL = "babel"
    DNSPYTHON = "dnspython"
    PORTALOCKER = "portalocker"
    COOKIECUTTER = "cookiecutter"
    PYJWT = "pyjwt"
    PYTHON_RSA = "python-rsa"
    MORE_ITERTOOLS = "more-itertools"
    SIMPY = "simpy"
    CLICK = "click"
    FABRIC = "fabric"
    JINJA = "jinja"
    FLASK = "flask"
    SQLPARSE = "sqlparse"
    MARSHMALLOW = "marshmallow"
    IMAPCLIENT = "imapclient"
    TINYDB = "tinydb"
    CACHETOOLS = "cachetools"
    VOLUPTUOUS = "voluptuous"
    PARSEL = "parsel"
    WCWIDTH = "wcwidth"
    DEPRECATED = "deprecated"
    
class RepoSplit(str, Enum):
    ALL = "all"
    MINITORCH = "minitorch"
    SIMPY = "simpy"
    LITE = "lite"

def read_yaml_config(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def validate_config(config: Dict[str, Any], required_keys: List[str]) -> None:
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing required keys in YAML config: {', '.join(missing_keys)}")
    
@app.command()
def clone(
    repo_split: RepoSplit = typer.Argument(..., help="Split of the repository"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory to clone repos")
):
    """
    Commit0 clone a repository.
    """
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
    repo_split: RepoSplit = typer.Argument(..., help="Split of the repository"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    num_workers: int = typer.Option(8, help="Number of workers"),
    backend: str = typer.Option("local", help="Backend to use for building")
):
    """
    Commit0 build a repository.
    """
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
    repo_name: AllRepos = typer.Argument(..., help="Name of the repository to get tests for")
):
    """
    Get tests for a Commit0 repository.
    """
    typer.echo(f"Getting tests for repository: {repo_name}")
    
    commit0.harness.get_pytest_ids.main(repo_name, stdout=True)

@app.command()
def test(
    repo_or_repo_path: str = typer.Argument(..., help="Directory of the repository to test"),
    branch: str = typer.Argument(..., help="Branch to test"),
    test_ids: str = typer.Argument(..., help="Test IDs to run"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(3600, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use")
):
    """
    Run tests on a Commit0 repository.
    """
    typer.echo(f"Running tests for repository: {repo_or_repo_path}")
    typer.echo(f"Branch: {branch}")
    typer.echo(f"Test IDs: {test_ids}")
    
    if branch.startswith("branch="):
        branch = branch[len("branch="):]
    
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
    repo_or_repo_path: str = typer.Argument(..., help="Directory of the repository to test"),
    test_ids: str = typer.Argument(..., help="Test IDs to run"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for testing"),
    timeout: int = typer.Option(1800, help="Timeout for tests in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use")
):
    """
    Run tests on the reference commit of a Commit0 repository.
    """
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
    repo_split: RepoSplit = typer.Argument(..., help="Split of the repository"),
    branch: str = typer.Argument(..., help="Branch to evaluate"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for evaluation"),
    timeout: int = typer.Option(1800, help="Timeout for evaluation in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    num_workers: int = typer.Option(8, help="Number of workers to use")
):
    """
    Evaluate a Commit0 repository.
    """
    typer.echo(f"Evaluating repository split: {repo_split}")
    typer.echo(f"Branch: {branch}")
    
    if branch.startswith("branch="):
        branch = branch[len("branch="):]
    
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
    repo_split: RepoSplit = typer.Argument(..., help="Split of the repository"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    backend: str = typer.Option("local", help="Backend to use for evaluation"),
    timeout: int = typer.Option(1800, help="Timeout for evaluation in seconds"),
    num_cpus: int = typer.Option(1, help="Number of CPUs to use"),
    num_workers: int = typer.Option(8, help="Number of workers to use")
):
    """
    Evaluate the reference commit of a Commit0 repository.
    """
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
    files: List[str] = typer.Argument(..., help="Files to lint. If not provided, all files will be linted."),
):
    """
    Lint given files if provided, otherwise lint all files in the base directory.
    """
    if files:
        for file in files:
            if not Path(file).is_file():
                raise FileNotFoundError(f"File not found: {file}")
        typer.echo(f"Linting specific files: {', '.join(files)}")
    else:
        typer.echo("Linting all files in the repository")
    
    commit0.harness.lint.main(files)

@app.command()
def save(
    repo_split: RepoSplit = typer.Argument(..., help="Split of the repository"),
    owner: str = typer.Argument(..., help="Owner of the repository"),
    branch: str = typer.Argument(..., help="Branch to save"),
    dataset_name: str = typer.Option("wentingzhao/commit0_docstring", help="Name of the Huggingface dataset"),
    dataset_split: str = typer.Option("test", help="Split of the Huggingface dataset"),
    base_dir: str = typer.Option("repos/", help="Base directory of repos"),
    github_token: str = typer.Option(None, help="GitHub token for authentication")
):
    """
    Save a Commit0 repository to GitHub.
    """
    typer.echo(f"Saving repository split: {repo_split}")
    typer.echo(f"Owner: {owner}")
    typer.echo(f"Branch: {branch}")
    
    if branch.startswith("branch="):
        branch = branch[len("branch="):]
    
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