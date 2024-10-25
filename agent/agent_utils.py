import bz2
import git
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import List
import fitz
from import_deps import ModuleSet
from graphlib import TopologicalSorter, CycleError
import yaml

from agent.class_types import AgentConfig

PROMPT_HEADER = ">>> Here is the Task:\n"
REFERENCE_HEADER = "\n\n>>> Here is the Reference for you to finish the task:\n"
REPO_INFO_HEADER = "\n\n>>> Here is the Repository Information:\n"
UNIT_TESTS_INFO_HEADER = "\n\n>>> Here are the Unit Tests Information:\n"
LINT_INFO_HEADER = "\n\n>>> Here is the Lint Information:\n"
SPEC_INFO_HEADER = "\n\n>>> Here is the Specification Information:\n"
IMPORT_DEPENDENCIES_HEADER = "\n\n>>> Here are the Import Dependencies:\n"
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


def collect_test_files(directory: str) -> list[str]:
    """Collect all the test files in the directory."""
    test_files = []
    subdirs = []

    # Walk through the directory
    for root, dirs, files in os.walk(directory):
        if root.endswith("/"):
            root = root[:-1]
        # Check if 'test' is part of the folder name
        if (
            "test" in os.path.basename(root).lower()
            or os.path.basename(root) in subdirs
        ):
            for file in files:
                # Process only Python files
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    test_files.append(file_path)
            for d in dirs:
                subdirs.append(d)

    return test_files


def collect_python_files(directory: str) -> list[str]:
    """List to store all the .py filenames"""
    python_files = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory):
        for file in files:
            # Check if the file ends with '.py'
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                python_files.append(file_path)

    return python_files


def _find_files_to_edit(base_dir: str, src_dir: str, test_dir: str) -> list[str]:
    """Identify files to remove content by heuristics.
    We assume source code is under [lib]/[lib] or [lib]/src.
    We exclude test code. This function would not work
    if test code doesn't have its own directory.

    Args:
    ----
        base_dir (str): The path to local library.
        src_dir (str): The directory containing source code.
        test_dir (str): The directory containing test code.

    Returns:
    -------
        list[str]: A list of files to be edited.

    """
    files = collect_python_files(os.path.join(base_dir, src_dir))
    test_files = collect_test_files(os.path.join(base_dir, test_dir))
    files = list(set(files) - set(test_files))

    # don't edit __init__ files
    files = [f for f in files if "__init__" not in f]
    # don't edit __main__ files
    files = [f for f in files if "__main__" not in f]
    # don't edit confest.py files
    files = [f for f in files if "conftest.py" not in f]
    return files


def ignore_cycles(graph: dict) -> list[str]:
    """Ignore the cycles in the graph."""
    ts = TopologicalSorter(graph)
    try:
        return list(ts.static_order())
    except CycleError as e:
        # print(f"Cycle detected: {e.args[1]}")
        # You can either break the cycle by modifying the graph or handle it as needed.
        # For now, let's just remove the first node in the cycle and try again.
        cycle_nodes = e.args[1]
        node_to_remove = cycle_nodes[0]
        # print(f"Removing node {node_to_remove} to resolve cycle.")
        graph.pop(node_to_remove, None)
        return ignore_cycles(graph)


def topological_sort_based_on_dependencies(
    pkg_paths: list[str],
) -> tuple[list[str], dict]:
    """Topological sort based on dependencies."""
    module_set = ModuleSet([str(p) for p in pkg_paths])

    import_dependencies = {}
    for path in sorted(module_set.by_path.keys()):
        module_name = ".".join(module_set.by_path[path].fqn)
        mod = module_set.by_name[module_name]
        try:
            imports = module_set.get_imports(mod)
            import_dependencies[path] = set([str(x) for x in imports])
        except Exception:
            import_dependencies[path] = set()

    import_dependencies_files = ignore_cycles(import_dependencies)

    return import_dependencies_files, import_dependencies


def get_target_edit_files(
    local_repo: git.Repo,
    src_dir: str,
    test_dir: str,
    branch: str,
    reference_commit: str,
    use_topo_sort_dependencies: bool = True,
) -> tuple[list[str], dict]:
    """Find the files with functions with the pass statement."""
    target_dir = str(local_repo.working_dir)
    files = _find_files_to_edit(target_dir, src_dir, test_dir)
    filtered_files = []
    for file_path in files:
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as file:
            content = file.read()
            if len(content.splitlines()) > 1500:
                continue
            if "    pass" in content:
                filtered_files.append(file_path)
    # Change to reference commit to get the correct dependencies
    local_repo.git.checkout(reference_commit)

    topological_sort_files, import_dependencies = (
        topological_sort_based_on_dependencies(filtered_files)
    )
    if len(topological_sort_files) != len(filtered_files):
        if len(topological_sort_files) < len(filtered_files):
            # Find the missing elements
            missing_files = set(filtered_files) - set(topological_sort_files)
            # Add the missing files to the end of the list
            topological_sort_files = topological_sort_files + list(missing_files)
        else:
            raise ValueError(
                "topological_sort_files should not be longer than filtered_files"
            )
    assert len(topological_sort_files) == len(
        filtered_files
    ), "all files should be included"

    # change to latest commit
    local_repo.git.checkout(branch)

    # Remove the base_dir prefix
    topological_sort_files = [
        file.replace(target_dir, "").lstrip("/") for file in topological_sort_files
    ]

    # Remove the base_dir prefix from import dependencies
    import_dependencies_without_prefix = {}
    for key, value in import_dependencies.items():
        key_without_prefix = key.replace(target_dir, "").lstrip("/")
        value_without_prefix = [v.replace(target_dir, "").lstrip("/") for v in value]
        import_dependencies_without_prefix[key_without_prefix] = value_without_prefix
    if use_topo_sort_dependencies:
        return topological_sort_files, import_dependencies_without_prefix
    else:
        filtered_files = [
            file.replace(target_dir, "").lstrip("/") for file in filtered_files
        ]
        return filtered_files, import_dependencies_without_prefix


def get_target_edit_files_from_patch(
    local_repo: git.Repo, patch: str, use_topo_sort_dependencies: bool = True
) -> tuple[list[str], dict]:
    """Get the target files from the patch."""
    working_dir = str(local_repo.working_dir)
    target_files = set()
    for line in patch.split("\n"):
        if line.startswith("+++") or line.startswith("---"):
            file_path = line.split()[1]
            if file_path.startswith("a/"):
                file_path = file_path[2:]
            if file_path.startswith("b/"):
                file_path = file_path[2:]
            target_files.add(file_path)

    target_files_list = list(target_files)
    target_files_list = [
        os.path.join(working_dir, file_path) for file_path in target_files_list
    ]

    if use_topo_sort_dependencies:
        topological_sort_files, import_dependencies = (
            topological_sort_based_on_dependencies(target_files_list)
        )
        if len(topological_sort_files) != len(target_files_list):
            if len(topological_sort_files) < len(target_files_list):
                missing_files = set(target_files_list) - set(topological_sort_files)
                topological_sort_files = topological_sort_files + list(missing_files)
            else:
                raise ValueError(
                    "topological_sort_files should not be longer than target_files_list"
                )
        assert len(topological_sort_files) == len(
            target_files_list
        ), "all files should be included"

        topological_sort_files = [
            file.replace(working_dir, "").lstrip("/") for file in topological_sort_files
        ]
        for key, value in import_dependencies.items():
            import_dependencies[key] = [
                v.replace(working_dir, "").lstrip("/") for v in value
            ]
        return topological_sort_files, import_dependencies
    else:
        target_files_list = [
            file.replace(working_dir, "").lstrip("/") for file in target_files_list
        ]
        return target_files_list, {}


def get_message(
    agent_config: AgentConfig,
    repo_path: str,
    test_files: list[str] | None = None,
) -> str:
    """Get the message to Aider."""
    prompt = f"{PROMPT_HEADER}" + agent_config.user_prompt

    #    if agent_config.use_unit_tests_info and test_file:
    #         unit_tests_info = (
    #             f"\n{UNIT_TESTS_INFO_HEADER} "
    #             + get_file_info(
    #                 file_path=Path(os.path.join(repo_path, test_file)), prefix=""
    #             )[: agent_config.max_unit_tests_info_length]
    #         )
    if agent_config.use_unit_tests_info and test_files:
        unit_tests_info = f"\n{UNIT_TESTS_INFO_HEADER} "
        for test_file in test_files:
            unit_tests_info += get_file_info(
                file_path=Path(os.path.join(repo_path, test_file)), prefix=""
            )
        unit_tests_info = unit_tests_info[: agent_config.max_unit_tests_info_length]
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

    if agent_config.use_spec_info:
        with bz2.open("spec.pdf.bz2", "rb") as in_file:
            with open("spec.pdf", "wb") as out_file:
                out_file.write(in_file.read())
        spec_info = (
            f"\n{SPEC_INFO_HEADER} "
            + get_specification(specification_pdf_path=Path(repo_path, "spec.pdf"))[
                : agent_config.max_spec_info_length
            ]
        )
    else:
        spec_info = ""

    message_to_agent = prompt + repo_info + unit_tests_info + spec_info

    return message_to_agent


def update_message_with_dependencies(message: str, dependencies: list[str]) -> str:
    """Update the message with the dependencies."""
    if len(dependencies) == 0:
        return message
    import_dependencies_info = f"\n{IMPORT_DEPENDENCIES_HEADER}"
    for dependency in dependencies:
        with open(dependency, "r") as file:
            import_dependencies_info += (
                f"\nHere is the content of the file {dependency}:\n{file.read()}"
            )
    message += import_dependencies_info
    return message


def get_specification(specification_pdf_path: Path) -> str:
    """Get the reference for a given specification PDF path."""
    # TODO: after pdf_to_text is available, use it to extract the text from the PDF
    # Open the specified PDF file
    document = fitz.open(specification_pdf_path)
    text = ""

    # Iterate through the pages
    for page_num in range(len(document)):
        page = document.load_page(page_num)  # loads the specified page
        text += page.get_text()  # type: ignore

    return text


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


def get_changed_files_from_commits(
    repo: git.Repo, commit1: str, commit2: str
) -> list[str]:
    """Get the changed files from two commits."""
    try:
        # Get the commit objects
        commit1_obj = repo.commit(commit1)
        commit2_obj = repo.commit(commit2)

        # Get the diff between the two commits
        diff = commit1_obj.diff(commit2_obj)

        # Extract the changed file paths
        changed_files = [item.a_path for item in diff]

        # Check if each changed file is a Python file
        python_files = [file for file in changed_files if file.endswith(".py")]

        # Update the changed_files list to only include Python files
        changed_files = python_files

        return changed_files
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


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


def get_lint_cmd(repo_name: str, use_lint_info: bool, commit0_config_file: str) -> str:
    """Generate a linting command based on whether to include files.

    Args:
    ----
        repo_name (str): The name of the repository.
        use_lint_info (bool): A flag indicating whether to include changed files in the lint command.
        commit0_config_file (str): The path to the commit0 dot file.

    Returns:
    -------
        str: The generated linting command string. If `use_lint_info` is True, the command includes
             the list of changed files. If False, returns an empty string.

    """
    lint_cmd = "python -m commit0 lint "
    if use_lint_info:
        lint_cmd += (
            repo_name + " --commit0-config-file " + commit0_config_file + " --files "
        )
    else:
        lint_cmd = ""
    return lint_cmd


def write_agent_config(agent_config_file: str, agent_config: dict) -> None:
    """Write the agent config to the file."""
    with open(agent_config_file, "w") as f:
        yaml.dump(agent_config, f)


def read_yaml_config(config_file: str) -> dict:
    """Read the yaml config from the file."""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"The config file '{config_file}' does not exist.")
    with open(config_file, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)
