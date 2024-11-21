# Agent for Commit0
This tool provides a command-line interface for configuring and running AI agents to assist with code development and testing.

## Quick Start
Configure an agent:
```bash
agent config [OPTIONS] AGENT_NAME
```

Run an agent on a specific branch:
```bash
agent run [OPTIONS] BRANCH
```

For more detailed information on available commands and options:
```bash
agent -h
agent config -h
agent run -h
```
## Configure an Agent
Use `agent config [OPTIONS] AGENT_NAME` to set up the configuration for an agent.
Available options include:

`--agent_name: str`: Agent to use, we only support [aider](https://aider.chat/) for now. [Default: `aider`]
`--model-name: str`: LLM model to use, check [here](https://aider.chat/docs/llms.html) for all supported models. [Default: `claude-3-5-sonnet-20240620`]
`--use-user-prompt: bool`: Use a custom prompt instead of the default prompt. [Default: `False`]
`--user-prompt: str`: The prompt sent to agent. [Default: See code for details.]
`--run-tests: bool`: Run tests after code modifications for feedback. You need to set up `docker` or `modal` before running tests, refer to commit0 docs. [Default `False`]
`--max-iteration: int`: Maximum number of agent iterations. [Default: `3`]
`--use-repo-info: bool`: Include the repository information. [Default: `False`]
`--max-repo-info-length: int`: Maximum length of the repository information to use. [Default: `10000`]
`--use-unit-tests-info: bool`: Include the unit tests information. [Default: `False`]
`--max-unit-tests-info-length: int`: Maximum length of the unit tests information to use. [Default: `10000`]
`--use-spec-info: bool`: Include the spec information. [Default: `False`]
`--max-spec-info-length: int`: Maximum length of the spec information to use. [Default: `10000`]
`--use-lint-info: bool`: Include the lint information. [Default: `False`]
`--max-lint-info-length: int`: Maximum length of the lint information to use. [Default: `10000`]
`--pre-commit-config-path: str`: Path to the pre-commit config file. This is needed for running `lint`. [Default: `.pre-commit-config.yaml`]
`--agent-config-file: str`: Path to write the agent config. [Default: `.agent.yaml`]
`--add-import-module-to-context: bool`: Add import module to context. [Default: `False`]
`--record-test-for-each-commit: bool`: Record test results for each commit. [Default: `False`], if set to `True`, the test results will be saved in `experiment_log_dir/eval_results.json`

## Running Agent
Use `agent run [OPTIONS] BRANCH` to execute an agent on a specific branch.
Available options include:

`--branch: str`: Branch to run the agent on, you can specific the name of the branch
`--backend: str`: Test backend to run the agent on, ignore this option if you are not adding `run_tests` option to agent. [Default: `modal`]
`--log-dir: str`: Log directory to store the logs. [Default: `logs/aider`]
`--max-parallel-repos: int`: Maximum number of repositories for agent to run in parallel. Running in sequential if set to 1. [Default: `1`]
`--display-repo-progress-num: int`: Number of repo progress displayed when running. [Default: `5`]


### Example: Running aider
Step 1: Configure aider: `agent config aider`
Step 2: Run aider on a branch: `agent run aider_branch`

### Other Agent:
Refer to `class Agents` in `agent/agents.py`. You can design your own agent by inheriting `Agents` class and implement the `run` method.

## Notes

### Automatically retry
Aider automatically retries certain API errors. For details, see [here](https://github.com/paul-gauthier/aider/blob/75e1d519da9b328b0eca8a73ee27278f1289eadb/aider/sendchat.py#L17).

### Parallelize agent running
When increasing --max-parallel-repos, be mindful of aider's [60-second retry timeout](https://github.com/paul-gauthier/aider/blob/75e1d519da9b328b0eca8a73ee27278f1289eadb/aider/sendchat.py#L39). Set this value according to your API tier to avoid RateLimitErrors stopping processes.

### Large files in repo
Currently, agent will skip file with more than 1500 lines. See `agent/agent_utils.py#L199` for details.

### Cost
Running a full `all` commit0 split costs approximately $100.

