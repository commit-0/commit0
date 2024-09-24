import os
import sys
import yaml
import multiprocessing
from tqdm import tqdm
import queue  # Add this import
from datasets import load_dataset
from git import Repo
from agent.commit0_utils import (
    args2string,
    create_branch,
    get_message,
    get_target_edit_files,
    get_lint_cmd,
)
from agent.agents import AiderAgents
from typing import Optional, Type
from types import TracebackType
from agent.class_types import AgentConfig
from commit0.harness.constants import SPLIT
from commit0.harness.get_pytest_ids import main as get_tests
from commit0.harness.constants import RUN_AIDER_LOG_DIR, RepoInstance
from commit0.cli import read_commit0_dot_file
import time
import random
import multiprocessing
from agent.display import TerminalDisplay

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


def read_yaml_config(config_file: str) -> dict:
    """Read the yaml config from the file."""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"The config file '{config_file}' does not exist.")
    with open(config_file, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def run_agent_for_repo(
    repo_base_dir: str,
    agent_config: AgentConfig,
    example: RepoInstance,
    update_queue: multiprocessing.Queue
) -> None:
    """Run Aider for a given repository."""
    # get repo info
    _, repo_name = example["repo"].split("/")
    update_queue.put(("start_repo", (repo_name, 0)))
    repo_name = repo_name.lower()
    if repo_name != "web3.py":
        repo_name = repo_name.replace(".", "-")

    # Call the commit0 get-tests command to retrieve test files
    test_files_str = get_tests(repo_name, verbose=0)
    test_files = sorted(list(set([i.split(":")[0] for i in test_files_str])))

    repo_path = os.path.join(repo_base_dir, repo_name)
    repo_path = os.path.abspath(repo_path)
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

    run_id = args2string(agent_config)
    run_id = run_id.replace("run_tests-1", "run_tests-0")
    # print(f"Agent is coding on branch: {run_id}", file=sys.stderr)
    create_branch(local_repo, run_id, example["base_commit"])
    latest_commit = local_repo.commit(run_id)
    # in cases where the latest commit of branch is not commit 0
    # set it back to commit 0
    # TODO: ask user for permission
    if latest_commit.hexsha != example["base_commit"]:
        local_repo.git.reset("--hard", example["base_commit"])
    target_edit_files = get_target_edit_files(repo_path)

    # Determine the total number of files (either test files or target files)
    total_files = len(test_files) if agent_config.run_tests else len(target_edit_files)

    # Notify the display to start tracking this repo, pass the total number of files
    update_queue.put(("start_repo", (repo_name, total_files)))
    
    with DirContext(repo_path):
        if agent_config is None:
            raise ValueError("Invalid input")

        if agent_config.run_tests:
            # when unit test feedback is available, iterate over test files
            for test_file in test_files:
                update_queue.put(("set_current_file", (repo_name, test_file)))
                sleep_time = random.randint(1,3) # Random sleep time between 1 and 5 seconds
                time.sleep(sleep_time)
                update_queue.put(("update_money_display", random.random()))
                continue
                test_cmd = (
                    f"python -m commit0 test {repo_path} {test_file} --branch {run_id} --backend {agent_config.backend}"
                )
                test_file_name = test_file.replace(".py", "").replace("/", "__")
                log_dir = RUN_AIDER_LOG_DIR / "with_tests" / test_file_name
                lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                message = get_message(agent_config, repo_path, test_file=test_file)
                agent.run(
                    message,
                    test_cmd,
                    lint_cmd,
                    target_edit_files,
                    log_dir,
                )
        else:
            # when unit test feedback is not available, iterate over target files to edit
            message = get_message(
                agent_config, repo_path, test_dir=example["test"]["test_dir"]
            )
            agent_config_log_file = os.path.abspath(
                RUN_AIDER_LOG_DIR / "no_tests" / ".agent.yaml"
            )
            os.makedirs(os.path.dirname(agent_config_log_file), exist_ok=True)
            # write agent_config to .agent.yaml
            with open(agent_config_log_file, "w") as agent_config_file:
                yaml.dump(agent_config, agent_config_file)

            for f in target_edit_files:
                update_queue.put(("set_current_file", (repo_name, f)))
                sleep_time = random.randint(1,3) # Random sleep time between 1 and 5 seconds
                time.sleep(sleep_time)
                update_queue.put(("update_money_display", random.random()))
                continue
                file_name = f.replace(".py", "").replace("/", "__")
                log_dir = RUN_AIDER_LOG_DIR / "no_tests" / file_name
                lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                agent.run(message, "", lint_cmd, [f], log_dir)
    update_queue.put(("finish_repo", repo_name))

def run_agent_test(agent_config_file: str) -> None:
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

    with TerminalDisplay(len(filtered_dataset)) as display:
        unstarted_repos = [example["repo"].split("/")[-1] for example in filtered_dataset]
        display.set_unstarted_repos(unstarted_repos)

        display.update_backend_display(agent_config.backend)
        total_money_spent = 0
        
        with multiprocessing.Manager() as manager:
            update_queue = manager.Queue()

            

            update_queue.put(("update_backend_display", agent_config.backend))
            with multiprocessing.Pool(processes=3) as pool:
                results = []

                for example in filtered_dataset:
                    result = pool.apply_async(
                        run_agent_for_repo,
                        args=(commit0_config["base_dir"], agent_config, example, update_queue)
                    )
                    results.append(result)

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
                                money_spent = data
                                total_money_spent += money_spent
                                display.update_money_display(total_money_spent)
                    except queue.Empty:
                        pass
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
                        money_spent = data
                        total_money_spent += money_spent
                        display.update_money_display(total_money_spent)

                for result in results:
                    result.get()