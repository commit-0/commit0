## Commit0

Commit0 provides several commands to facilitate the process of cloning, building, testing, and evaluating repositories. Here's an overview of the available commands:

### Setup

Use `commit0 setup [OPTIONS] REPO_SPLIT` to clone a repository split.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `repo_split` | str | Split of repositories to clone | |
| `--dataset-name` | str | Name of the Huggingface dataset | `wentingzhao/commit0_combined` |
| `--dataset-split` | str | Split of the Huggingface dataset | `test` |
| `--base-dir` | str | Base directory to clone repos to | `repos/` |
| `--commit0-config-file` | str | Storing path for stateful commit0 configs | `.commit0.yaml` |

### Build

Use `commit0 build [OPTIONS]` to build the Commit0 split chosen in the Setup stage.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `--num-workers` | int | Number of workers | `8` |
| `--commit0-config-file` | str | Path to the commit0 dot file | `.commit0.yaml` |
| `--verbose` | int | Verbosity level (1 or 2) | `1` |

### Get Tests

Use `commit0 get-tests REPO_NAME` to get tests for a Commit0 repository.

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `repo_name` | str | Name of the repository to get tests for | |

### Test

Use `commit0 test [OPTIONS] REPO_OR_REPO_PATH [TEST_IDS]` to run tests on a Commit0 repository.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `repo_or_repo_path` | str | Directory of the repository to test | |
| `test_ids` | str | Test IDs to run | |
| `--branch` | str | Branch to test | |
| `--backend` | str | Backend to use for testing | `modal` |
| `--timeout` | int | Timeout for tests in seconds | `1800` |
| `--num-cpus` | int | Number of CPUs to use | `1` |
| `--reference` | bool | Test the reference commit | `False` |
| `--coverage` | bool | Get coverage information | `False` |
| `--rebuild` | bool | Rebuild an image | `False` |
| `--commit0-config-file` | str | Path to the commit0 dot file | `.commit0.yaml` |
| `--verbose` | int | Verbosity level (1 or 2) | `1` |
| `--stdin` | bool | Read test names from stdin | `False` |

### Evaluate

Use `commit0 evaluate [OPTIONS]` to evaluate the Commit0 split chosen in the Setup stage.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `--branch` | str | Branch to evaluate | |
| `--backend` | str | Backend to use for evaluation | `modal` |
| `--timeout` | int | Timeout for evaluation in seconds | `1800` |
| `--num-cpus` | int | Number of CPUs to use | `1` |
| `--num-workers` | int | Number of workers to use | `8` |
| `--reference` | bool | Evaluate the reference commit | `False` |
| `--coverage` | bool | Get coverage information | `False` |
| `--commit0-config-file` | str | Path to the commit0 dot file | `.commit0.yaml` |
| `--rebuild` | bool | Rebuild images | `False` |

### Lint

Use `commit0 lint [OPTIONS] REPO_OR_REPO_DIR` to lint files in a repository.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `repo_or_repo_dir` | str | Directory of the repository to test | |
| `--files` | List[Path] | Files to lint (optional) | |
| `--commit0-config-file` | str | Path to the commit0 dot file | `.commit0.yaml` |
| `--verbose` | int | Verbosity level (1 or 2) | `1` |

### Save

Use `commit0 save [OPTIONS] OWNER BRANCH` to save the Commit0 split to GitHub.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `owner` | str | Owner of the repository | |
| `branch` | str | Branch to save | |
| `--github-token` | str | GitHub token for authentication | |
| `--commit0-config-file` | str | Path to the commit0 dot file | `.commit0.yaml` |

## Agent

### Config

Use `agent config [OPTIONS] AGENT_NAME` to set up the configuration for an agent.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `agent_name` | str | Agent to use, we only support [aider](https://aider.chat/) for now. | `aider` |
| `--model-name` | str | LLM model to use, check [here](https://aider.chat/docs/llms.html) for all supported models. | `claude-3-5-sonnet-20240620` |
| `--use-user-prompt` | bool | Use a custom prompt instead of the default prompt. | `False` |
| `--user-prompt` | str | The prompt sent to agent. | See code for details. |
| `--run-tests` | bool | Run tests after code modifications for feedback. You need to set up `docker` or `modal` before running tests, refer to commit0 docs. | `False` |
| `--max-iteration` | int | Maximum number of agent iterations. | `3` |
| `--use-repo-info` | bool | Include the repository information. | `False` |
| `--max-repo-info-length` | int | Maximum length of the repository information to use. | `10000` |
| `--use-unit-tests-info` | bool | Include the unit tests information. | `False` |
| `--max-unit-tests-info-length` | int | Maximum length of the unit tests information to use. | `10000` |
| `--use-spec-info` | bool | Include the spec information. | `False` |
| `--max-spec-info-length` | int | Maximum length of the spec information to use. | `10000` |
| `--use-lint-info` | bool | Include the lint information. | `False` |
| `--max-lint-info-length` | int | Maximum length of the lint information to use. | `10000` |
| `--pre-commit-config-path` | str | Path to the pre-commit config file. This is needed for running `lint`. | `.pre-commit-config.yaml` |
| `--agent-config-file` | str | Path to write the agent config. | `.agent.yaml` |

### Running

Use `agent run [OPTIONS] BRANCH` to execute an agent on a specific branch.
Available options include:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `branch` | str | Branch for the agent to commit changes | |
| `--backend` | str | Test backend to run the agent on, ignore this option if you are not adding `run_tests` option to agent. | `modal` |
| `--log-dir` | str | Log directory to store the logs. | `logs/aider` |
| `--max-parallel-repos` | int | Maximum number of repositories for agent to run in parallel. Running in sequential if set to 1. | `1` |
| `--display-repo-progress-num` | int | Number of repo progress displayed when running. | `5` |
