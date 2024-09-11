# How to run baseline

Step 1: Go to `config/aider.yaml` and change the config

Step 2: Run the following command

```bash
python baselines/run_aider.py --config-name aider
```

## Config

aider_config:
  model_name: LLM model name

context_config:

- use_repo_info: Whether to use repo info
    Repo info
    skeleton of the repo(filenames under each dir)
    function stubs
- use_unit_tests: Whether to use unit tests: unit_tests that target
will be tested with
- use_reference: Whether to use reference: reference doc/pdf/website
