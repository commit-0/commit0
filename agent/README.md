# How to run baseline

Step 1: Go to `config/aider.yaml` and change the config

Step 2: Run the following command

```bash
python baselines/run_aider.py
```

## Config

`commit0_config`:

- `base_dir`: Repos dir. Default `repos`.
- `dataset_name`: commit0 HF dataset name. Default: `wentingzhao/commit0_docstring`.
- `dataset_split`: commit0 dataset split. Default: `test`.
- `repo_split`: commit0 repo split. Default: `simpy`.
- `num_workers`: number of workers to run in parallel. Default: `10`.

`aider_config`:

- `llm_name`: LLM model name. Default: `claude-3-5-sonnet-20240620`.
- `use_user_prompt`: Whether to use user prompt. Default: `false`.
- `user_prompt`: User prompt. Default: `""`.
- `use_repo_info`: Whether to use repo info. Default: `false`.
  - Repo info
  - skeleton of the repo(filenames under each dir)
  - function stubs

- `use_unit_tests_info`: Whether to use unit tests: unit_tests that target will be tested with. Default: `false`.
- `use_reference_info`: Whether to use reference: reference doc/pdf/website. Default: `false`.
- `use_lint_info`: Whether to use lint: lint info. Default: `false`.
- `pre_commit_config_path`: Path to pre-commit config. Default: `.pre-commit-config.yaml`.
- `run_tests`: Whether to run tests. Default: `true`.
- `max_repo_info_length`: Max length of repo info. Default: `10000`.
- `max_unit_tests_info_length`: Max length of unit tests info. Default: `10000`.
- `max_reference_info_length`: Max length of reference info. Default: `10000`.
- `max_lint_info_length`: Max length of lint info. Default: `10000`.










Error Section



Running the agent

Run with Tmux!

process_max_worker set to 3....

currently not handling file with more than 1500 lines...