import typer
from agent.run_agent_no_rich import run_agent as run_agent_no_rich
from agent.run_agent import run_agent
from commit0.harness.constants import RUN_AGENT_LOG_DIR
import subprocess
from agent.agent_utils import write_agent_config

agent_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_show_locals=False,
    help="""
    This is the command for running agent on Commit-0.

    See the website at https://commit-0.github.io/ for documentation and more information about Commit-0.
    """,
)


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    ORANGE = "\033[95m"


def check_aider_path() -> None:
    """Code adapted from https://github.com/modal-labs/modal-client/blob/a8ddd418f8c65b7e168a9125451eeb70da2b6203/modal/cli/entry_point.py#L55

    Checks whether the `aider` executable is on the path and usable.
    """
    url = "https://aider.chat/docs/install.html"
    try:
        subprocess.run(["aider", "--help"], capture_output=True)
        # TODO(erikbern): check returncode?
        return
    except FileNotFoundError:
        typer.echo(
            typer.style(
                "The `aider` command was not found on your path!", fg=typer.colors.RED
            )
            + "\n"
            + typer.style(
                "You may need to add it to your path or use `python -m run_agent` as a workaround.",
                fg=typer.colors.RED,
            )
        )
    except PermissionError:
        typer.echo(
            typer.style("The `aider` command is not executable!", fg=typer.colors.RED)
            + "\n"
            + typer.style(
                "You may need to give it permissions or use `python -m run_agent` as a workaround.",
                fg=typer.colors.RED,
            )
        )
    typer.echo(f"See more information here:\n\n{url}")
    typer.echo("─" * 80)  # Simple rule to separate content


def highlight(text: str, color: str) -> str:
    """Highlight text with a color."""
    return f"{color}{text}{Colors.RESET}"


@agent_app.command()
def config(
    agent_name: str = typer.Argument(
        ...,
        help=f"Agent to use, we only support {highlight('aider', Colors.ORANGE)} for now",
    ),
    model_name: str = typer.Option(
        "claude-3-5-sonnet-20240620",
        help="Model to use, check https://aider.chat/docs/llms.html for more information",
    ),
    use_user_prompt: bool = typer.Option(
        False,
        help="Use the user prompt instead of the default prompt",
    ),
    user_prompt: str = typer.Option(
        "Here is your task:\nYou need to complete the implementations for all functions (i.e., those with pass statements) and pass the unit tests.\nDo not change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.\nWhen you generate code, you must maintain the original formatting of the function stubs (such as whitespaces), otherwise we will not able to search/replace blocks for code modifications, and therefore you will receive a score of 0 for your generated code.",
        help="User prompt to use",
    ),
    topo_sort_dependencies: bool = typer.Option(
        True,
        help="Topologically sort the dependencies of the repository",
    ),
    add_import_module_to_context: bool = typer.Option(
        True,
        help="Add the import module code to the context",
    ),
    run_tests: bool = typer.Option(
        False,
        help="Run the tests after the agent is done",
    ),
    max_iteration: int = typer.Option(
        3,
        help="Maximum number of iterations to run",
    ),
    use_repo_info: bool = typer.Option(
        False,
        help="Use the repository information",
    ),
    max_repo_info_length: int = typer.Option(
        10000,
        help="Maximum length of the repository information to use",
    ),
    use_unit_tests_info: bool = typer.Option(
        False,
        help="Use the unit tests information",
    ),
    max_unit_tests_info_length: int = typer.Option(
        10000,
        help="Maximum length of the unit tests information to use",
    ),
    use_spec_info: bool = typer.Option(
        False,
        help="Use the spec information",
    ),
    max_spec_info_length: int = typer.Option(
        10000,
        help="Maximum length of the spec information to use",
    ),
    use_lint_info: bool = typer.Option(
        False,
        help="Use the lint information",
    ),
    max_lint_info_length: int = typer.Option(
        10000,
        help="Maximum length of the lint information to use",
    ),
    run_entire_dir_lint: bool = typer.Option(
        False,
        help="Run the lint on the entire directory",
    ),
    record_test_for_each_commit: bool = typer.Option(
        False,
        help="Record the test for each commit",
    ),
    pre_commit_config_path: str = typer.Option(
        ".pre-commit-config.yaml",
        help="Path to the pre-commit config file",
    ),
    agent_config_file: str = typer.Option(
        ".agent.yaml",
        help="Path to the agent config file",
    ),
) -> None:
    """Configure the agent."""
    if agent_name == "aider":
        check_aider_path()

    if use_user_prompt:
        user_prompt = typer.prompt("Please enter your user prompt")

    agent_config = {
        "agent_name": agent_name,
        "model_name": model_name,
        "use_user_prompt": use_user_prompt,
        "user_prompt": user_prompt,
        "run_tests": run_tests,
        "use_topo_sort_dependencies": topo_sort_dependencies,
        "add_import_module_to_context": add_import_module_to_context,
        "max_iteration": max_iteration,
        "use_repo_info": use_repo_info,
        "max_repo_info_length": max_repo_info_length,
        "use_unit_tests_info": use_unit_tests_info,
        "max_unit_tests_info_length": max_unit_tests_info_length,
        "use_spec_info": use_spec_info,
        "max_spec_info_length": max_spec_info_length,
        "use_lint_info": use_lint_info,
        "max_lint_info_length": max_lint_info_length,
        "run_entire_dir_lint": run_entire_dir_lint,
        "pre_commit_config_path": pre_commit_config_path,
        "record_test_for_each_commit": record_test_for_each_commit,
    }

    write_agent_config(agent_config_file, agent_config)


@agent_app.command()
def run(
    branch: str = typer.Argument(
        ...,
        help="Branch for the agent to commit changes",
    ),
    override_previous_changes: bool = typer.Option(
        False,
        help="If override the previous agent changes on `branch` or run the agent continuously on the new changes",
    ),
    backend: str = typer.Option(
        "modal",
        help="Test backend to run the agent on, ignore this option if you are not adding `test` option to agent",
    ),
    agent_config_file: str = typer.Option(
        ".agent.yaml",
        help="Path to the agent config file",
    ),
    commit0_config_file: str = typer.Option(
        ".commit0.yaml",
        help="Path to the commit0 config file",
    ),
    log_dir: str = typer.Option(
        str(RUN_AGENT_LOG_DIR.resolve()),
        help="Log directory to store the logs",
    ),
    max_parallel_repos: int = typer.Option(
        1,
        help="Maximum number of repositories for agent to run in parallel",
    ),
    display_repo_progress_num: int = typer.Option(
        5,
        help="Display the agent progress",
    ),
    show_rich_progress: bool = typer.Option(
        True,
        help="Display the agent progress with rich",
    ),
) -> None:
    """Run the agent on the repository."""
    if show_rich_progress:
        run_agent(
            branch,
            override_previous_changes,
            backend,
            agent_config_file,
            commit0_config_file,
            log_dir,
            max_parallel_repos,
            display_repo_progress_num,
        )
    else:
        run_agent_no_rich(
            branch,
            override_previous_changes,
            backend,
            agent_config_file,
            commit0_config_file,
            log_dir,
            max_parallel_repos,
        )
