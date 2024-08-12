# spec2repo

We set up a task where, given a specification, the goal is to produce an implementation of the specification.
Specifically, we are interested in converting library specifications to implementations (i.e., repositories).
We lay out the steps to create a spec2repo example and perform an evaluation on the example using the SWE-bench framework.

First, to install required packages,
```
pip install -r requirements.txt
```

Please provide the following information for the list of repositories in a JSON file,
```
repos.json
{"name":[repo_name],"commit":null,"tag":"v4.8.0","setup":["python -m pip install --upgrade pip twine","pip install poetry","poetry install"]}
```
There are two options to specify the version of the library:
you can either provide a specific commit or a specific tag. You cannot specify both at the same time.
Finally, include the commands that sets up the library from a local repository.
For example, to create an example for the ``msiemens/tinydb`` with version 4.8, 
```
repos.json
{"name":"msiemens/tinydb","commit":null,"tag":"v4.8.0","setup":["python -m pip install --upgrade pip twine","pip install poetry","poetry install"]}
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
