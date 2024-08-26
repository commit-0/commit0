# spec2repo

We set up a task where, given a specification, the goal is to produce an implementation of the specification.
Specifically, we are interested in converting library specifications to implementations (i.e., repositories).
We lay out the steps to create a spec2repo example and perform an evaluation on the example using the SWE-bench framework.

First, to install required packages,
```
pip install -r requirements.txt
```

Please provide the following information for the list of repositories in a YAML file,
```
repos.yml
0: # just an index
  name: [repository_name] # in the form of {organization_name}/{library_name}
  commit: [commit_sha]
  tag: [version_tag]
  setup:
    - [command_1]
    - [command_2]
    - ...
```
There are two options to specify the version of the library:
you can either provide a specific commit or a specific tag. You cannot specify both at the same time.
Finally, include the commands that sets up the library from a local repository.
For example, to create an example for the ``msiemens/tinydb`` with version 4.8, 
```
repos.yml
0:
  name: "msiemens/tinydb"
  commit: null
  tag: "v4.8.0"
  setup:
    - "python -m pip install --upgrade pip twine"
    - "pip install poetry"
    - "poetry install"
```

We are now ready to generate the dataset. Before that, add your GitHub token in the environment.
```
export GITHUB_TOKEN=[github_token]
```
Now run,
```
python create-data/build_dataset.py repos.json --hf_name wentingzhao/spec2repo
```
where ``repos.json`` is the file we specified above, and ``wentingzhao/spec2repo`` is where you want to upload the dataset on HF.
This command produces the base commit (with function body removed), gold patch that passes all unit tests, and all test function names.
Note that this script will create a fork for the libaray. The fork will be created under organization ``spec2repo``.
You can change the organization to somewhere else. But if you want to create a fork under ``spec2repo``, please contact Wenting Zhao to be added to the organization.

Now that dataset has been generated, we move on to using SWE-bench to perform an evaluation.
First, follow the instructions in the [Docker setup guide](https://docs.docker.com/engine/install/) to install Docker on your machine.
If you're setting up on Linux, we recommend seeing the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) as well.

To install SWE-bench:
```bash
git clone https://github.com/princeton-nlp/SWE-bench.git
cd SWE-bench
pip install -e .
```

Now, let's add a configuration file to build a DOCKER environment for the library in a YAML file:
```
configs/specs.yml
spec2repo/tinydb:
  "1.0":
    python: 3.11
    install: "python -m pip install --upgrade pip twine; pip install poetry; poetry install"
    test_cmd: "pytest"
```
To make this for your own library, leave the ``1.0`` unchanged, specify the Python version with ``python``, and how to locally build the library with ``install``, and how to run tests with ``test_cmd``.

You also need to write your own function to process the test logs. Please add your function in ``configs/log_parsers.py``. The function should take in a log text file and return a dictionary that maps from a test function to its test stutas such as passed or failed. After that, update the global variable ``ADD_MAP_REPO_TO_PARSER``.
```
configs/log_parsers.py
def parse_log_tinydb(log: str) -> dict[str, str]:
    """
    Parser for test logs generated with TinyDB framework

    Args:
        log (str): log content
    Returns:
        dict: test case to test status mapping
    """
    test_status_map = {}
    pattern = r"^(.*\/.*)::(.*)\s+\w+\s+\[\s*(\d+%)\]$"
    for line in log.split("\n"):
        line = line.strip()
        m = re.match(pattern, line)
        if m:
            line = line.split()
            test, value = line[:2]
            if value == "PASSED":
                test_status_map[test] = TestStatus.PASSED.value
            else:
                test_status_map[test] = TestStatus.FAILED.value
    return test_status_map

ADD_MAP_REPO_TO_PARSER = {
    "spec2repo/tinydb": parse_log_tinydb,
}
```

Finally, to run evaluation for the created example using the gold patch with the following script:
```
python run.py \
    --dataset_name wentingzhao/spec2repo \
    --split train \
    --max_workers 2 \
    --predictions_path 'gold' \
    --instance_ids spec2repo__tinydb-01 \
    --run_id validate-gold \
    --spec_config configs/specs.yml
```

## Baseline
### Baseline Input & Output

A simple baseline evaluation can be described like this
```python
def run_baseline(base_model, agent, prompt, context, target, error_history) -> test_results, error_message:
    pass
```

**Input**

`base_model`: base LLM, e.g. `gpt-4o`, `claude-3-5-sonnet-20240620`

`agent`: agent, e.g. `aider`, `opendevin`, `None`

`prompt`: the prompt/instruction given to `agent`/`base_model`

`context`: there are 3 types of context
- `context-type-1`: reference doc/pdf/website
- `context-type-2`: unit_tests that target will be tested with
- `context-type-3`: Repo info
  - skeleton of the repo(filenames under each dir)
  - function stubs
  - function name in each file(granularity need to be specified)

`target`: target function or file for agent or base_model to complete
`edit_history`: entire edit histories, each contains previous implementation, updated implementation and corresponding error message

**Output**

`test_results`: WIP
`error_message`: WIP

## Baseline Evaluation & Ablation

There are mainly 3 axes.
- different `base_model`
- different `agent`
- different `context`

Current priority is to run `gpt-4o` + `aider` with certain `context` to get first baseline result.
