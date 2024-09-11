import re
import subprocess
from pathlib import Path
from typing import List

PROMPT_HEADER = ">>> Here is the Task:\n"
REFERENCE_HEADER = "\n\n>>> Here is the Reference for you to finish the task:\n"
REPO_INFO_HEADER = "\n\n>>> Here is the Repository Information:\n"
UNIT_TESTS_INFO_HEADER = "\n\n>>> Here are the Unit Tests Information:\n"
EDIT_HISTORY_HEADER = "\n\n>>> Here is the Edit History:\n"

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


def find_files_with_error(target_dir: str) -> List[str]:
    """Find the files with the error 'NotImplementedError('IMPLEMENT ME HERE')'."""
    # The grep command
    command = f"grep -R -l \"NotImplementedError('IMPLEMENT ME HERE')\" {target_dir}"

    # Run the command and capture the output
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    # Split the output into lines and remove the base_dir prefix
    files = result.stdout.strip().split("\n")

    return files


def get_reference(specification_url: str) -> str:
    """Get the reference for a given specification URL."""
    return f"/web {specification_url}"
