import os
import sys
import hydra
import multiprocessing
from datasets import load_dataset
from git import Repo
from baselines.commit0_utils import (
    args2string,
    create_branch,
    get_message,
    get_target_edit_files,
)
from baselines.agents import AiderAgents
from typing import Optional, Type
from types import TracebackType
from hydra.core.config_store import ConfigStore
from baselines.class_types import AgentConfig, Commit0Config
from commit0.harness.constants import SPLIT
from commit0.harness.get_pytest_ids import main as get_tests
from commit0.harness.constants import RUN_AIDER_LOG_DIR, RepoInstance
from tqdm import tqdm


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
    commit0_config: Commit0Config,
    agent_config: AgentConfig,
    example: RepoInstance,
) -> None:
    """Run Aider for a given repository."""
    # get repo info
    _, repo_name = example["repo"].split("/")

    repo_name = repo_name.lower()
    repo_name = repo_name.replace(".", "-")

    # Call the commit0 get-tests command to retrieve test files
    test_files_str = get_tests(repo_name, stdout=False)
    test_files = sorted(list(set([i.split(":")[0] for i in test_files_str])))

    repo_path = os.path.join(commit0_config.base_dir, repo_name)
    repo_path = os.path.abspath(repo_path)
    try:
        local_repo = Repo(repo_path)
    except Exception:
        raise Exception(
            f"{repo_path} is not a git repo. Check if base_dir is correctly specified."
        )

    target_edit_files = get_target_edit_files(repo_path)

    if agent_config.agent_name == "aider":
        agent = AiderAgents(agent_config.max_iteration, agent_config.model_name)
    else:
        raise NotImplementedError(
            f"{agent_config.agent_name} is not implemented; please add your implementations in baselines/agents.py."
        )

    run_id = args2string(agent_config)
    print(f"Agent is coding on branch: {run_id}", file=sys.stderr)
    create_branch(local_repo, run_id, example["base_commit"])
    latest_commit = local_repo.commit(run_id)
    # in cases where the latest commit of branch is not commit 0
    # set it back to commit 0
    # TODO: ask user for permission
    if latest_commit.hexsha != example["base_commit"]:
        local_repo.git.reset("--hard", example["base_commit"])

    with DirContext(repo_path):
        if commit0_config is None or agent_config is None:
            raise ValueError("Invalid input")

        message = get_message(agent_config, repo_path, example["test"]["test_dir"])

        if agent_config.use_lint_info:
            lint_cmd = "pre-commit run --config ../../.pre-commit-config.yaml --files"
        else:
            lint_cmd = ""

        if agent_config.run_tests:
            # when unit test feedback is available, iterate over test files
            for test_file in test_files:
                test_cmd = f"python -m commit0 test {repo_path} {run_id} {test_file}"
                test_file_name = test_file.replace(".py", "").replace("/", "__")
                log_dir = RUN_AIDER_LOG_DIR / "with_tests" / test_file_name

                agent.run(
                    message,
                    test_cmd,
                    lint_cmd,
                    target_edit_files,
                    log_dir,
                )
        else:
            # when unit test feedback is not available, iterate over target files to edit
            for f in target_edit_files:
                file_name = f.replace(".py", "").replace("/", "__")
                log_dir = RUN_AIDER_LOG_DIR / "no_tests" / file_name

                agent.run(message, "", lint_cmd, [f], log_dir)


def main() -> None:
    """Main function to run Aider for a given repository.

    Will run in parallel for each repo.
    """
    cs = ConfigStore.instance()
    cs.store(name="user", node=Commit0Config)
    cs.store(name="user", node=AgentConfig)
    hydra.initialize(version_base=None, config_path="configs")
    config = hydra.compose(config_name="agent")
    commit0_config = Commit0Config(**config.commit0_config)
    agent_config = AgentConfig(**config.agent_config)

    dataset = load_dataset(
        commit0_config.dataset_name, split=commit0_config.dataset_split
    )
    filtered_dataset = [
        example
        for example in dataset
        if commit0_config.repo_split == "all"
        or (
            isinstance(example, dict)
            and "repo" in example
            and isinstance(example["repo"], str)
            and example["repo"].split("/")[-1]
            in SPLIT.get(commit0_config.repo_split, [])
        )
    ]
    assert len(filtered_dataset) > 0, "No examples available"

    if len(filtered_dataset) > 1:
        sys.stdout = open(os.devnull, "w")

    with tqdm(
        total=len(filtered_dataset), smoothing=0, desc="Running Aider for repos"
    ) as pbar:
        with multiprocessing.Pool(processes=commit0_config.num_workers) as pool:
            results = []

            # Use apply_async to submit jobs and add progress bar updates
            for example in filtered_dataset:
                result = pool.apply_async(
                    run_agent_for_repo,
                    args=(commit0_config, agent_config, example),
                    callback=lambda _: pbar.update(
                        1
                    ),  # Update progress bar on task completion
                )
                results.append(result)

            for result in results:
                result.wait()


if __name__ == "__main__":
    main()
