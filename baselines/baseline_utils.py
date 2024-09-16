import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from baselines.class_types import AiderConfig

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


def get_prompt(file_list: str) -> str:
    """Get the prompt for the Aider model."""
    return """Here is the Task:\n Your task is to iteratively implement the each function that is 'NotImplementedError('IMPLEMENT ME HERE')' in these files until there are no more 'NotImplementedError('IMPLEMENT ME HERE')' and pass the unit tests.
Make sure you read the files carefully.
Your output should be the edited code files.
Use the above instructions to modify the supplied files: {file_list}
Do not change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.
Only use standard python libraries, do not suggest installing any packages.
""".format(file_list=file_list)


def get_target_edit_files_cmd_args(target_dir: str) -> str:
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

    return " ".join(files)


def get_message_to_aider(
    aider_config: AiderConfig,
    target_edit_files_cmd_args: str,
    repo_path: str,
    ds: Dict[str, Any],
) -> str:
    """Get the message to Aider."""
    # support context for aider
    if aider_config.use_user_prompt:
        assert (
            aider_config.user_prompt != ""
        ), "You choose to use custom user prompt, but it is empty"
        prompt = f"{PROMPT_HEADER} " + aider_config.user_prompt
    else:
        prompt = f"{PROMPT_HEADER} " + get_prompt(target_edit_files_cmd_args)

    if aider_config.use_unit_tests_info and ds["test"]["test_dir"]:
        unit_tests_info = (
            f"\n{UNIT_TESTS_INFO_HEADER} "
            + get_dir_info(
                dir_path=Path(os.path.join(repo_path, ds["test"]["test_dir"])),
                prefix="",
                include_stubs=True,
            )[: aider_config.max_unit_tests_info_length]
        )
    else:
        unit_tests_info = ""

    # TODO: assuming we have specification, which we currently do not have
    if aider_config.use_reference_info and ds["specification"]:
        reference = (
            f"\n{REFERENCE_HEADER} "
            + get_reference(ds["specification"])[
                : aider_config.max_reference_info_length
            ]
        )
    else:
        reference = ""

    if aider_config.use_repo_info:
        repo_info = (
            f"\n{REPO_INFO_HEADER} "
            + get_dir_info(
                dir_path=Path(repo_path), prefix="", max_depth=2, include_stubs=False
            )[: aider_config.max_repo_info_length]
        )
    else:
        repo_info = ""

    message_to_aider = prompt + reference + repo_info + unit_tests_info

    return message_to_aider


def get_reference(specification_pdf_path: str) -> str:
    """Get the reference for a given specification PDF path."""
    # TODO: after pdf_to_text is available, use it to extract the text from the PDF
    return f"/pdf {specification_pdf_path}"