# Agent for Commit0
`agent config [OPTIONS] AGENT_NAME`: Setup the config you want agent to run with
`agent run [OPTIONS] BRANCH`: running agent on specific branch

You can also run the following command to know more information
```bash
agent -h
agent config -h
agent run -h
```
## Configure Agent
Here are all configs you can choose when you run `agent config [OPTIONS] AGENT_NAME`

`--agent_name: str`: Agent to use, we only support [aider](https://aider.chat/) for now. [Default: `aider`]
`--model-name: str`: Model to use, check [here](https://aider.chat/docs/llms.html) for more information. [Default: `claude-3-5-sonnet-20240620`]
`--use-user-prompt: bool`: Use the user prompt instead of the default prompt. [Default: `False`]
`--user-prompt: str`: The prompt sent to agent. [Default: Refer to code.]
`--run-tests: bool`: Run the tests after the agent modified the code to get feedback. [Default `False`]
`--max-iteration: int`: Maximum number of iterations for agent to run. [Default: `3`]
`--use-repo-info: bool`: Use the repository information. [Default: `False`]
`--max-repo-info-length: int`: Maximum length of the repository information to use. [Default: `10000`]
`--use-unit-tests-info: bool`: Use the unit tests information. [Default: `False`]
`--max-unit-tests-info-length: int`: Maximum length of the unit tests information to use. [Default: `10000`]
`--use-spec-info: bool`: Use the spec information. [Default: `False`]
`--max-spec-info-length: int`: Maximum length of the spec information to use. [Default: `10000`]
`--use-lint-info: bool`: Use the lint information. [Default: `False`]
`--max-lint-info-length: int`: Maximum length of the lint information to use. [Default: `10000`]
`--pre-commit-config-path: str`: Path to the pre-commit config file. [Default: `.pre-commit-config.yaml`]
`--agent-config-file: str`: Path to write the agent config. [Default: `.agent.yaml`]

## Running Agent
Here are all configs you can choose when you run `agent run [OPTIONS] BRANCH`

`--branch: str`: Branch to run the agent on, you can specific the name of the branch
`--backend: str`: Test backend to run the agent on, ignore this option if you are not adding `run_tests` option to agent. [Default: `modal`]
`--log-dir: str`: Log directory to store the logs. [Default: `logs/aider`]
`--max-parallel-repos: int`: Maximum number of repositories for agent to run in parallel. Running in sequential if set to 1. [Default: `1`]
`--display-repo-progress-num: int`: Number of repo progress displayed when running. [Default: `5`]


### Agent Example: aider
Step 1: `agent config aider`
Step 2: `agent run aider_branch`

### Other Agent:
Refer to `class Agents` in `agent/agents.py`. You can design your own agent by inheriting `Agents` class and implement the `run` method.

## Notes

### Automatically retry
Please refer to [here](https://github.com/paul-gauthier/aider/blob/75e1d519da9b328b0eca8a73ee27278f1289eadb/aider/sendchat.py#L17) for the type fo API error that aider will automatically retry.

### Large files in repo
Currently, agent will skip file with more than 1500 lines.(check `agent/agent_utils.py#L199`)

