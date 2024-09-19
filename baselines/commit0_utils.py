import git
import os
import re
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import List

from baselines.class_types import AgentConfig

PROMPT_HEADER = ">>> Here is the Task:\n"
REFERENCE_HEADER = "\n\n>>> Here is the Reference for you to finish the task:\n"
REPO_INFO_HEADER = "\n\n>>> Here is the Repository Information:\n"
UNIT_TESTS_INFO_HEADER = "\n\n>>> Here are the Unit Tests Information:\n"
LINT_INFO_HEADER = "\n\n>>> Here is the Lint Information:\n"

# prefix components:
space = "    "
branch = "│   "
# pointers:
tee = "├── "
last = "└── "


def extract_function_stubs(file_path: Path) -> List[str]:
    """Extract function stubs from a Python file, including type hints."""
    with open(file_path, "r") as file:
        content = file.read()

    # Regular expression to match function definitions with optional type hints
    # This pattern now stops at the colon that ends the function signature
    pattern = (
        r"def\s+(\w+)\s*\(((?:[^()]*|\([^()]*\))*)\)\s*(?:->\s*([\w\[\],\s|]+))?\s*:"
    )
    matches = re.findall(pattern, content)

    stubs = []
    for name, args, return_type in matches:
        # Process arguments to include type hints
        processed_args = []
        for arg in args.split(","):
            arg = arg.strip()
            if ":" in arg:
                arg_name, arg_type = arg.split(":", 1)
                processed_args.append(f"{arg_name.strip()}: {arg_type.strip()}")
            else:
                processed_args.append(arg)

        args_str = ", ".join(processed_args)

        # Include return type if present
        return_annotation = f" -> {return_type.strip()}" if return_type else ""

        stubs.append(f"def {name}({args_str}){return_annotation}: ...")

    return stubs


def get_dir_info(
    dir_path: Path,
    prefix: str = "",
    max_depth: int = 10,
    include_stubs: bool = False,
    current_depth: int = 0,
    ignore_dot_files: bool = True,
) -> str:
    """A recursive generator, given a directory Path object will yield a visual
    tree structure line by line with each line prefixed by the same characters.

    Args:
    ----
    dir_path (Path): The directory to traverse
    prefix (str): The prefix to use for the current level
    max_depth (int): The maximum depth to traverse (default: infinite)
    current_depth (int): The current depth of traversal (used internally)
    ignore_dot_files (bool): Whether to ignore files/directories starting with a dot (default: True)
    include_stubs (bool): Whether to include function stubs for Python files (default: True)

    """
    if current_depth >= max_depth:
        return ""

    contents = list(dir_path.iterdir())

    if ignore_dot_files:
        contents = [c for c in contents if not c.name.startswith(".")]

    tree_string = []
    # contents each get pointers that are ├── with a final └── :
    pointers = [tee] * (len(contents) - 1) + [last]
    for pointer, path in zip(pointers, contents):
        tree_string.append(prefix + pointer + path.name)
        if path.is_dir():
            extension = branch if pointer == tee else space
            tree_string.append(
                get_dir_info(
                    path,
                    prefix=prefix + extension,
                    max_depth=max_depth,
                    include_stubs=include_stubs,
                    current_depth=current_depth + 1,
                    ignore_dot_files=ignore_dot_files,
                )
            )
        elif include_stubs and path.suffix == ".py":
            stubs = extract_function_stubs(path)
            for stub in stubs:
                tree_string.append(prefix + space + space + stub)
    return "\n".join(filter(None, tree_string))


def get_file_info(file_path: Path, prefix: str = "") -> str:
    """Return the contents of a file with a given prefix."""
    tree_string = [tee + file_path.name]
    stubs = extract_function_stubs(file_path)
    for stub in stubs:
        tree_string.append(prefix + space + space + stub)
    return "\n".join(filter(None, tree_string))


def get_target_edit_files(target_dir: str) -> list[str]:
    """Find the files with the error 'NotImplementedError('IMPLEMENT ME
    HERE')'.
    """
    # The grep command
    command = f"grep -R -l \"NotImplementedError('IMPLEMENT ME HERE')\" {target_dir}"

    # Run the command and capture the output
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    # Split the output into lines and remove the base_dir prefix
    files = result.stdout.strip().split("\n")

    # Remove the base_dir prefix
    files = [file.replace(target_dir, "").lstrip("/") for file in files]

    # Only keep python files
    files = [file for file in files if file.endswith(".py")]

    return files


def get_message(
    agent_config: AgentConfig,
    repo_path: str,
    test_dir: str,
) -> str:
    """Get the message to Aider."""
    prompt = f"{PROMPT_HEADER}" + agent_config.user_prompt

    if agent_config.use_unit_tests_info and test_dir:
        unit_tests_info = (
            f"\n{UNIT_TESTS_INFO_HEADER} "
            + get_dir_info(
                dir_path=Path(os.path.join(repo_path, test_dir)),
                prefix="",
                include_stubs=True,
            )[: agent_config.max_unit_tests_info_length]
        )
    else:
        unit_tests_info = ""

    # TODO: assuming we have specification, which we currently do not have
    if agent_config.use_repo_info:
        repo_info = (
            f"\n{REPO_INFO_HEADER} "
            + get_dir_info(
                dir_path=Path(repo_path), prefix="", max_depth=2, include_stubs=False
            )[: agent_config.max_repo_info_length]
        )
    else:
        repo_info = ""

    message_to_agent = prompt + repo_info + unit_tests_info

    return message_to_agent


def get_reference(specification_pdf_path: str) -> str:
    """Get the reference for a given specification PDF path."""
    # TODO: after pdf_to_text is available, use it to extract the text from the PDF
    return f"/pdf {specification_pdf_path}"


def create_branch(repo: git.Repo, branch: str, from_commit: str) -> None:
    """Create a new branch or switch to an existing branch.

    Parameters
    ----------
    repo : git.Repo
        The repository object.
    branch : str
        The name of the branch to create or switch to.
    from_commit : str
        from which commit to create the branch

    Returns
    -------
    None

    Raises
    ------
    RuntimeError
        If creating or switching to the branch fails.

    """
    try:
        # Check if the branch already exists
        if branch in repo.heads:
            repo.git.checkout(branch)
        else:
            repo.git.checkout(from_commit)
            repo.git.checkout("-b", branch)
    except git.exc.GitCommandError as e:  # type: ignore
        raise RuntimeError(f"Failed to create or switch to branch '{branch}': {e}")


def args2string(agent_config: AgentConfig) -> str:
    """Converts specific fields from an `AgentConfig` object into a formatted string.

    Args:
    ----
        agent_config (AgentConfig): A dataclass object containing configuration
        options for an agent.

    Returns:
    -------
        str: A string representing the selected key-value pairs from the `AgentConfig`
        object, joined by double underscores.

    """
    arg_dict = asdict(agent_config)
    result_list = []
    keys_to_collect = ["model_name", "run_tests", "use_lint_info", "use_spec_info"]
    for key in keys_to_collect:
        value = arg_dict[key]
        if isinstance(value, bool):
            if value:
                value = "1"
            else:
                value = "0"
        result_list.append(f"{key}-{value}")
    concatenated_string = "__".join(result_list)
    return concatenated_string


def get_changed_files(repo: git.Repo) -> list[str]:
    """Get a list of files that were changed in the latest commit of the provided Git repository.

    Args:
    ----
        repo (git.Repo): An instance of GitPython's Repo object representing the Git repository.

    Returns:
    -------
        list[str]: A list of filenames (as strings) that were changed in the latest commit.

    """
    latest_commit = repo.head.commit
    # Get the list of files changed in the latest commit
    files_changed = latest_commit.stats.files
    files_changed = [str(one) for one in files_changed]
    return files_changed


def get_lint_cmd(repo: git.Repo, use_lint_info: bool) -> str:
    """Generate a linting command based on whether to include files changed in the latest commit.

    Args:
    ----
        repo (git.Repo): An instance of GitPython's Repo object representing the Git repository.
        use_lint_info (bool): A flag indicating whether to include changed files in the lint command.

    Returns:
    -------
        str: The generated linting command string. If `use_lint_info` is True, the command includes
             the list of changed files. If False, returns an empty string.

    """
    lint_cmd = "python -m commit0 lint "
    if use_lint_info:
        lint_cmd += " ".join(get_changed_files(repo))
    else:
        lint_cmd = ""
    return lint_cmd
