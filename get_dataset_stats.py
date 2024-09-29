import re
import os
import glob
import ast
import subprocess
import json
import shutil
import argparse
import pypdf
import tqdm
import csv

from datasets import load_dataset
from transformers import AutoTokenizer

from commit0.harness.constants import SPLIT
from commit0.harness.utils import clone_repo
from commit0.cli import write_commit0_dot_file

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

analysis_files_path = "/share/rush/commit0_analysis_temp"

def collect_test_files(directory):
    # List to store all the filenames
    test_files = []
    subdirs = []

    # Walk through the directory
    for root, dirs, files in os.walk(directory):
        if root.endswith("/"):
            root = root[:-1]
        # Check if 'test' is part of the folder name
        if 'test' in os.path.basename(root).lower() or os.path.basename(root) in subdirs:
            for file in files:
                # Process only Python files
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    test_files.append(file_path)
            for d in dirs:
                subdirs.append(d)

    return test_files


def collect_python_files(directory):
    # List to store all the .py filenames
    python_files = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory):
        for file in files:
            # Check if the file ends with '.py'
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                python_files.append(file_path)

    return python_files

def _find_files_to_edit(base_dir: str, src_dir: str, test_dir: str) -> list[str]:
    """Identify files to remove content by heuristics.
    We assume source code is under [lib]/[lib] or [lib]/src.
    We exclude test code. This function would not work
    if test code doesn't have its own directory.

    Args:
    ----
        base_dir (str): the path to local library.

    Return:
    ------
        files (list[str]): a list of files to be edited.

    """
    files = collect_python_files(os.path.join(base_dir, src_dir))
    test_files = collect_test_files(os.path.join(base_dir, test_dir))
    files = list(set(files) - set(test_files))

    # don't edit __init__ files
    files = [f for f in files if "__init__" not in f]
    # don't edit __main__ files
    files = [f for f in files if "__main__" not in f]
    # don't edit confest.py files
    files = [f for f in files if "conftest.py" not in f]
    return files
    

def get_dataset_stats(
    base_dir, src_dir, test_dir,
    spec_filename,
    tokenizer,
):
    repo_name = os.path.basename(base_dir.rstrip("/"))
    files_to_edit = _find_files_to_edit(base_dir, src_dir, test_dir)

    fns_to_edit = []
    for filename in files_to_edit:
        try:
            code = open(filename, encoding="utf-8").read()
        except Exception as e:
            print(f"{e}: Trouble opening {filename}")
            continue
        try:
            code_tree = ast.parse(code)
        except Exception as e:
            print(
                f"{e}: Trouble parsing {filename}"
            )
            continue
        filename = os.path.basename(filename)
        for node in ast.walk(code_tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    child.parent_class = node.name
            elif isinstance(node, ast.FunctionDef) and len(node.body) > 0:
                classname = ""
                if hasattr(node, "parent_class"):
                    classname = f"{node.parent_class}."
                for child in node.body:
                    child.parent_function = f"{classname}{node.name}"
            elif isinstance(node, ast.Pass):
                if hasattr(node, "parent_function"):
                    fns_to_edit.append(
                        f"{filename}::{node.parent_function}"
                    )
                elif hasattr(node, "parent_class"):
                    fns_to_edit.append(
                        f"{filename}::{node.parent_class}"
                    )

    # Get spec metrics
    concatted_spec = ""
    reader = pypdf.PdfReader(spec_filename)
    for p_idx, page in enumerate(reader.pages):
        try:
            concatted_spec += page.extract_text()
        except Exception as e:
            print(f"{e}: Could not load page {p_idx} of {spec_filename}, excluding...")


    repo_tests = subprocess.run(['commit0', 'get-tests', repo_name], capture_output=True, text=True).stdout.strip()

    dataset_metrics = {
        "repo_name": repo_name,
        "no_fns_to_edit": len(fns_to_edit),
        "no_tokens_in_spec": tokenizer(
            concatted_spec, return_tensors="pt"
        ).input_ids.shape[-1],
        "no_files_to_edit": len(files_to_edit),
        "no_unit_tests": len(repo_tests.splitlines())
    }
    return dataset_metrics, fns_to_edit


def get_impls(
    path_to_repo_src,
    files_to_edit,
):
    fn_impls = {}
    for filename in files_to_edit:
        try:
            code = open(os.path.join(path_to_repo_src, filename), encoding="utf-8").read()
        except Exception as e:
            print(f"{e}: Trouble opening {os.path.join(path_to_repo_src, filename)}")
            continue
        try:
            code_tree = ast.parse(code)
        except Exception as e:
            print(
                f"{e}: Trouble parsing {os.path.join(path_to_repo_src, filename)}"
            )
            continue
        code_lines = code.splitlines(keepends=True)
        for node in ast.walk(code_tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    child.parent_class = node.name
            elif isinstance(node, ast.FunctionDef) and len(node.body) > 0:
                classname = ""
                if hasattr(node, "parent_class"):
                    classname = f"{node.parent_class}."
                if len(node.body) > 0:
                    start_idx = sum(len(line) for line in code_lines[:node.body[0].lineno-1]) + node.body[0].col_offset
                    end_idx =  sum(len(line) for line in code_lines[:node.body[-1].end_lineno-1]) + node.body[-1].end_col_offset
                    fn_impls[f"{filename}::{classname}{node.name}"] = code[start_idx:end_idx]
    return fn_impls

def get_coverage_info(path_to_logs, repo_name, branch_name, files_to_edit):
    coverage_info = {} # unit test -> [ fnname ]
    for pytest_hash in os.listdir(path_to_logs):
        if not os.path.exists(os.path.join(path_to_logs, pytest_hash, "eval.sh")):
            continue
        eval_script = open(os.path.join(path_to_logs, pytest_hash, "eval.sh")).read()
        testname = re.search(r"([\S]+) > test_output", eval_script).group(1)

        if not os.path.exists(os.path.join(path_to_logs, pytest_hash, "coverage.json")): continue
        coverage_info[testname] = []
        coverage_file_path = os.path.join(path_to_logs, pytest_hash, "coverage.json")
        coverage_report = json.load(open(coverage_file_path))
        for filename, file_coverage in coverage_report['files'].items():
            if filename not in files_to_edit: continue
            for function in file_coverage["functions"]:
                coverage_info[testname].append(f"{filename}::{function}")
    return coverage_info

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--do_setup", action="store_true", help="Run commit0 setup with specified split"
    )
    parser.add_argument(
        "--get_dataset_metrics",
        action="store_true",
        help="Get difficulty metrics of blank repository",
    )
    parser.add_argument(
        "--get_coverage_info",
        action="store_true",
        help="Get pytest results from reference",
    )
    parser.add_argument("--split", type=str, help="all or lite")

    parser.add_argument(
        "--tokenizer_name", type=str, default="meta-llama/Meta-Llama-3.1-8B-Instruct"
    )
    parser.add_argument(
        "--overwrite_previous_eval",
        action="store_true",
        help="Overwrite cached pytest info"
        # TODO add finer granularity so can specify which ones to overwrite
    )

    return parser.parse_args()


def main(args):
    global analysis_files_path

    commit0_dataset_name = "wentingzhao/commit0_combined"
    dataset = load_dataset(commit0_dataset_name, split="test")  # type: ignore

    # os.system(
    #     f"commit0 setup all --base-dir {analysis_files_path}/repos "
    #     f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
    # )

    repo_to_files_to_edit = {}
    # tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name)
    # output_file = "dataset_metrics.csv"
    # with open(output_file, 'w') as wf:
    #     csv_writer = csv.DictWriter(wf, fieldnames=["repo_name", "no_fns_to_edit", "no_files_to_edit", "no_tokens_in_spec", "no_unit_tests"])
    #     csv_writer.writeheader()
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_name not in SPLIT["lite"]:
            continue

        base_dir = os.path.join(
            analysis_files_path, "repos", repo_name
        )
        source_code_folder = os.path.join(
            analysis_files_path, "repos", repo_name, example["src_dir"]
        )
        test_dir = os.path.join(
            analysis_files_path, "repos", repo_name, example["test"]['test_dir']
        )
    #         spec_filepath = os.path.join(
    #             analysis_files_path, "repos", repo_name, "spec.pdf"
    #         )
    #         datasaset_metrics, files_to_edit = get_dataset_stats(
    #             base_dir, source_code_folder, test_dir,
    #             spec_filepath,
    #             tokenizer,
    #         )
    #         csv_writer.writerow(datasaset_metrics)
    #         print(datasaset_metrics)
        files_to_edit = _find_files_to_edit(base_dir, source_code_folder, test_dir)
        repo_to_files_to_edit[repo_name] = [filename[len(base_dir)+1:] for filename in files_to_edit]

    branch_name = "reference"
    org_name = f"commit0_{args.split}"
    commit0_dot_file_path = os.path.join(
        analysis_files_path, "repos", org_name, branch_name, ".commit0.yaml"
    )
    submission_repos_path = os.path.join(
        analysis_files_path, "repos", org_name, branch_name
    )

    os.system(
        f"commit0 setup lite --base-dir {submission_repos_path} "
        f"--commit0-dot-file-path {commit0_dot_file_path}"
    )
    coverage_output_file = "coverage_info.json"
    coverage_details = {}
    
    # get coverage and pytest info for each repo
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_name not in SPLIT["lite"]:
            continue
        path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
        existing_tests_to_fnnames = get_coverage_info(path_to_logs, repo_name, branch_name, repo_to_files_to_edit[repo_name])
        repo_tests = subprocess.run(['commit0', 'get-tests', repo_name], capture_output=True, text=True).stdout.strip()
        for testname in repo_tests.splitlines():
            if testname.strip() not in existing_tests_to_fnnames:
                command = (
                    f"commit0 test {repo_name} {testname} --reference --coverage "
                    f"--commit0-dot-file-path {commit0_dot_file_path}"
                )
                print(command)
                os.system(command)
        tests_to_fnnames = get_coverage_info(path_to_logs, repo_name, branch_name, repo_to_files_to_edit[repo_name])
        base_dir = os.path.join(
            analysis_files_path, "repos", repo_name
        )
        fnnames_to_impls = get_impls(base_dir, repo_to_files_to_edit[repo_name])
        coverage_details[repo_name] = {}
        for testname, fnnames in tests_to_fnnames.items():
            coverage_details[repo_name][testname] = []
            for fnname in fnnames:
                if fnname in fnnames_to_impls:
                    coverage_details[repo_name][testname].append(fnname, fnnames_to_impls[fnname])
                else:
                    coverage_details[repo_name][testname].append((fnname, None))

    json.dump(
        coverage_details, open(coverage_output_file, "w"), indent=4
    )
    print(f"Saved coverage info to {coverage_output_file}")


main(get_args())
