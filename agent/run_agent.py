import os
import yaml
import multiprocessing
from datasets import load_dataset
from git import Repo
from agent.agent_utils import (
    create_branch,
    get_message,
    get_target_edit_files,
    get_lint_cmd,
    read_yaml_config,
)
from agent.agents import AiderAgents
from typing import Optional, Type, cast
from types import TracebackType
from agent.class_types import AgentConfig
from commit0.harness.constants import SPLIT
from commit0.harness.get_pytest_ids import main as get_tests
from commit0.harness.constants import RUN_AGENT_LOG_DIR, RepoInstance
from commit0.cli import read_commit0_dot_file
from pathlib import Path
from datetime import datetime
from agent.display import TerminalDisplay
import queue
import time


class DirContext:
    def __init__(self, d: str):
        self.dir = d
        self.cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self.dir)

    def __exit__(
        self,
        exctype: Optional[Type[BaseException]],
        excinst: Optional[BaseException],
        exctb: Optional[TracebackType],
    ) -> None:
        os.chdir(self.cwd)


def run_agent_for_repo(
    repo_base_dir: str,
    agent_config: AgentConfig,
    example: RepoInstance,
    update_queue: multiprocessing.Queue,
    branch: str,
    override_previous_changes: bool = False,
    backend: str = "modal",
    log_dir: str = str(RUN_AGENT_LOG_DIR.resolve()),
) -> None:
    """Run Aider for a given repository."""
    # get repo info
    _, repo_name = example["repo"].split("/")

    # before starting, display all information to terminal
    original_repo_name = repo_name
    update_queue.put(("start_repo", (original_repo_name, 0)))

    # repo_name = repo_name.lower()
    # repo_name = repo_name.replace(".", "-")

    repo_path = os.path.join(repo_base_dir, repo_name)
    repo_path = os.path.abspath(repo_path)

    target_edit_files = get_target_edit_files(
        repo_path, example["src_dir"], example["test"]["test_dir"]
    )
    # Call the commit0 get-tests command to retrieve test files
    test_files_str = get_tests(repo_name, verbose=0)
    test_files = sorted(list(set([i.split(":")[0] for i in test_files_str])))

    try:
        local_repo = Repo(repo_path)
    except Exception:
        raise Exception(
            f"{repo_path} is not a git repo. Check if base_dir is correctly specified."
        )

    if agent_config.agent_name == "aider":
        agent = AiderAgents(agent_config.max_iteration, agent_config.model_name)
    else:
        raise NotImplementedError(
            f"{agent_config.agent_name} is not implemented; please add your implementations in baselines/agents.py."
        )

    # # if branch_name is not provided, create a new branch name based on agent_config
    # if branch is None:
    #     branch = args2string(agent_config)

    create_branch(local_repo, branch, example["base_commit"])

    # in cases where the latest commit of branch is not commit 0
    # set it back to commit 0
    latest_commit = local_repo.commit(branch)
    if latest_commit.hexsha != example["base_commit"] and override_previous_changes:
        local_repo.git.reset("--hard", example["base_commit"])

    # prepare the log dir
    experiment_log_dir = (
        Path(log_dir)
        / repo_name
        / branch
        / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )
    experiment_log_dir.mkdir(parents=True, exist_ok=True)

    # write agent_config to .agent.yaml in the log_dir for record
    agent_config_log_file = experiment_log_dir / ".agent.yaml"
    with open(agent_config_log_file, "w") as agent_config_file:
        yaml.dump(agent_config, agent_config_file)

    # TODO: make this path more general
    commit0_dot_file_path = str(Path(repo_path).parent.parent / ".commit0.yaml")

    with DirContext(repo_path):
        if agent_config is None:
            raise ValueError("Invalid input")

        if agent_config.run_tests:
            update_queue.put(("start_repo", (original_repo_name, len(test_files))))
            # when unit test feedback is available, iterate over test files
            for test_file in test_files:
                update_queue.put(("set_current_file", (repo_name, test_file)))
                test_cmd = f"python -m commit0 test {repo_path} {test_file} --branch {branch} --backend {backend} --commit0-dot-file-path {commit0_dot_file_path}"
                test_file_name = test_file.replace(".py", "").replace("/", "__")
                test_log_dir = experiment_log_dir / test_file_name
                lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                message = get_message(agent_config, repo_path, test_file=test_file)

                # display the test file to terminal
                agent_return = agent.run(
                    message,
                    test_cmd,
                    lint_cmd,
                    target_edit_files,
                    test_log_dir,
                    test_first=True,
                )
                # after running the agent, update the money display
                update_queue.put(
                    (
                        "update_money_display",
                        (repo_name, test_file, agent_return.last_cost),
                    )
                )
        else:
            # when unit test feedback is not available, iterate over target files to edit
            message = get_message(
                agent_config, repo_path, test_dir=example["test"]["test_dir"]
            )

            update_queue.put(
                ("start_repo", (original_repo_name, len(target_edit_files)))
            )
            for f in target_edit_files:
                update_queue.put(("set_current_file", (repo_name, f)))
                file_name = f.replace(".py", "").replace("/", "__")
                file_log_dir = experiment_log_dir / file_name
                lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                agent_return = agent.run(message, "", lint_cmd, [f], file_log_dir)
                update_queue.put(
                    (
                        "update_money_display",
                        (repo_name, file_name, agent_return.last_cost),
                    )
                )
    update_queue.put(("finish_repo", original_repo_name))


def run_agent(
    branch: str,
    override_previous_changes: bool,
    backend: str,
    agent_config_file: str,
    log_dir: str,
    max_parallel_repos: int,
    display_repo_progress_num: int,
) -> None:
    """Main function to run Aider for a given repository."""
    config = read_yaml_config(agent_config_file)

    agent_config = AgentConfig(**config)

    commit0_config = read_commit0_dot_file(".commit0.yaml")

    dataset = load_dataset(
        commit0_config["dataset_name"], split=commit0_config["dataset_split"]
    )
    filtered_dataset = [
        example
        for example in dataset
        if commit0_config["repo_split"] == "all"
        or (
            isinstance(example, dict)
            and "repo" in example
            and isinstance(example["repo"], str)
            and example["repo"].split("/")[-1]
            in SPLIT.get(commit0_config["repo_split"], [])
        )
    ]
    assert len(filtered_dataset) > 0, "No examples available"

    # if len(filtered_dataset) > 1:
    #     sys.stdout = open(os.devnull, "w")

    with TerminalDisplay(len(filtered_dataset)) as display:
        not_started_repos = [
            cast(RepoInstance, example)["repo"].split("/")[-1]
            for example in filtered_dataset
        ]
        display.set_not_started_repos(not_started_repos)

        start_time = time.time()

        display.update_repo_progress_num(
            min(display_repo_progress_num, max_parallel_repos)
        )
        display.update_backend_display(backend)
        display.update_log_dir_display(log_dir)
        display.update_agent_display(
            agent_config.agent_name,
            agent_config.model_name,
            agent_config.run_tests,
            agent_config.use_repo_info,
            agent_config.use_unit_tests_info,
            agent_config.use_spec_info,
            agent_config.use_lint_info,
        )
        display.update_branch_display(branch)
        with multiprocessing.Manager() as manager:
            update_queue = manager.Queue()
            with multiprocessing.Pool(processes=max_parallel_repos) as pool:
                results = []

                # Use apply_async to submit jobs and add progress bar updates
                for example in filtered_dataset:
                    result = pool.apply_async(
                        run_agent_for_repo,
                        args=(
                            commit0_config["base_dir"],
                            agent_config,
                            cast(RepoInstance, example),
                            update_queue,
                            branch,
                            override_previous_changes,
                            backend,
                            log_dir,
                        ),
                    )
                    results.append(result)

                last_time_update = 0
                while any(not r.ready() for r in results):
                    try:
                        while not update_queue.empty():
                            action, data = update_queue.get_nowait()
                            if action == "start_repo":
                                repo_name, total_files = data
                                display.start_repo(repo_name, total_files)
                            elif action == "finish_repo":
                                repo_name = data
                                display.finish_repo(repo_name)
                            elif action == "set_current_file":
                                repo_name, file_name = data
                                display.set_current_file(repo_name, file_name)
                            elif action == "update_money_display":
                                repo_name, file_name, money_spent = data
                                display.update_money_display(
                                    repo_name, file_name, money_spent
                                )
                    except queue.Empty:
                        pass

                    # Update time display every second
                    current_time = time.time()
                    if current_time - last_time_update >= 1:
                        elapsed_time = int(current_time - start_time)
                        display.update_time_display(elapsed_time)
                        last_time_update = current_time

                    time.sleep(0.1)  # Small delay to prevent busy-waiting

                # Final update after all repos are processed
                while not update_queue.empty():
                    action, data = update_queue.get()
                    if action == "start_repo":
                        repo_name, total_files = data
                        display.start_repo(repo_name, total_files)
                    elif action == "finish_repo":
                        repo_name = data
                        display.finish_repo(repo_name)
                    elif action == "set_current_file":
                        repo_name, file_name = data
                        display.set_current_file(repo_name, file_name)
                    elif action == "update_money_display":
                        repo_name, file_name, money_spent = data
                        display.update_money_display(repo_name, file_name, money_spent)

                # Final time update
                elapsed_time = int(time.time() - start_time)
                display.update_time_display(elapsed_time)

                for result in results:
                    result.get()
