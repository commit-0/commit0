import os
import yaml
import multiprocessing
from tqdm import tqdm
from datasets import load_dataset
from git import Repo
from agent.agent_utils import (
    args2string,
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
    branch: Optional[str] = None,
    override_previous_changes: bool = False,
    backend: str = "modal",
    log_dir: str = str(RUN_AGENT_LOG_DIR.resolve()),
) -> None:
    """Run Aider for a given repository."""
    # get repo info
    _, repo_name = example["repo"].split("/")
    print("Working on repo: ", repo_name)

    # repo_name = repo_name.lower()
    # repo_name = repo_name.replace(".", "-")

    repo_path = os.path.join(repo_base_dir, repo_name)
    repo_path = os.path.abspath(repo_path)

    # get target files to edit and test files to run
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

    # if branch_name is not provided, create a new branch name based on agent_config
    if branch is None:
        branch = args2string(agent_config)

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
            # when unit test feedback is available, iterate over test files
            for test_file in test_files:
                test_cmd = f"python -m commit0 test {repo_path} {test_file} --branch {branch} --backend {backend} --commit0-dot-file-path {commit0_dot_file_path}"
                test_file_name = test_file.replace(".py", "").replace("/", "__")
                test_log_dir = experiment_log_dir / test_file_name
                lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                message = get_message(agent_config, repo_path, test_file=test_file)
                _ = agent.run(
                    message,
                    test_cmd,
                    lint_cmd,
                    target_edit_files,
                    test_log_dir,
                    test_first=True,
                )
                # cost = agent_return.last_cost
        else:
            # when unit test feedback is not available, iterate over target files to edit
            message = get_message(
                agent_config, repo_path, test_dir=example["test"]["test_dir"]
            )
            for f in target_edit_files:
                file_name = f.replace(".py", "").replace("/", "__")
                file_log_dir = experiment_log_dir / file_name
                lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                _ = agent.run(message, "", lint_cmd, [f], file_log_dir)
                # cost = agent_return.last_cost


def run_agent(
    branch: str,
    override_previous_changes: bool,
    backend: str,
    agent_config_file: str,
    log_dir: str,
    max_parallel_repos: int,
) -> None:
    """Main function to run Aider for a given repository.

    Will run in parallel for each repo.
    """
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

    with tqdm(
        total=len(filtered_dataset), smoothing=0, desc="Running Aider for repos"
    ) as pbar:
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
                        branch,
                        override_previous_changes,
                        backend,
                        log_dir,
                    ),
                    callback=lambda _: pbar.update(
                        1
                    ),  # Update progress bar on task completion
                )
                results.append(result)

            for result in results:
                result.wait()
