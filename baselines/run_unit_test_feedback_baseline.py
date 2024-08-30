import argparse
import logging
import subprocess
import os
import re

import git
from datasets import load_dataset

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, required=True, help="The name of the model to use.")
    parser.add_argument("--dataset_name", type=str, required=True, help="The name of the dataset to use (via the datasets library).")
    parser.add_argument("--dataset_config_name", type=str, default=None, help="The configuration name of the dataset to use (via the datasets library).")
    parser.add_argument("--dataset_split", type=str, default=None, help="Which split of the dataset to load.")
    parser.add_argument("--max_retry", type=int, default=10, help="max retry for each unit test")
    parser.add_argument("--instance_ids", nargs="+", type=str, help="Instance IDs to run (space separated)")
    args = parser.parse_args()

    if args.dataset_name.endswith('json'):
        ds = load_dataset('json', data_files=args.dataset_name, split="train")
    else:
        ds = load_dataset(args.dataset_name, args.dataset_config_name, split=args.dataset_split)

    pattern = re.compile(r"""(?:[^\s']+|'(?:\\.|[^'\\])*')""")
    for example in ds:
        if example["instance_id"] in args.instance_ids:
            repo_name = re.search(r'__(.*?)\-', example["instance_id"]).group(1)
            code_path = os.path.abspath('run_aider.py')
            path = os.path.abspath(os.path.join('tmp', repo_name))
            os.chdir(path)
            repo = git.Repo(path)
            repo.git.reset('--hard', example["base_commit"])
            venv_dir = os.path.join(path, 'venv', 'bin')
            python_path = venv_dir + os.sep + 'python'
            cmd = python_path + ' -m pip install aider-chat'
            cmd = pattern.findall(cmd)
            subprocess.run(cmd, check=True, text=True, capture_output=True)
            aider_path = os.path.join(venv_dir, 'aider')
            tests = set([x.split("::")[0] for x in example["FAIL_TO_PASS"]])
            print(tests)
            for test_name in tests:
                pytest_path = venv_dir + os.sep + 'pytest'
                test_name = os.path.join(path, test_name)
                logger.info(f"working on {test_name}")
                #cmd = f"{python_path} {code_path} {args.model_name} '{pytest_path} {test_name}' {args.max_retry}"
                cmd = f"{aider_path} --model gpt-4o-mini --test-cmd '{pytest_path} {test_name}' --auto-test --test --yes"
                cmd = pattern.findall(cmd)
                cmd = [x.replace("\"", "").replace("\'", "") for x in cmd]
                try:
                    result = subprocess.run(cmd, check=True)
                except subprocess.CalledProcessError as e:
                    logger.info(f"Command failed with exit code {e.returncode}")
                    logger.info(f"STDOUT: {e.stdout}")
                    logger.info(f"STDERR: {e.stderr}")


if __name__ == '__main__':
    main()
