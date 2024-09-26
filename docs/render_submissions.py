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


def get_pytest_info(path_to_logs, repo_name, branch_name):
    pytest_info = {}
    for pytest_hash in os.listdir(path_to_logs):
        eval_script = open(os.path.join(path_to_logs, pytest_hash, "eval.sh")).read()
        testname = re.search(r"([\S]+) > test_output", eval_script).group(1)
        patch_diff = open(os.path.join(path_to_logs, pytest_hash, "patch.diff")).read()
        pytest_info[testname] = {
            "hash": pytest_hash,
            "patch_diff": patch_diff,
            "failures": {},
        }
        report_file_path = os.path.join(path_to_logs, pytest_hash, "report.json")
        if not os.path.exists(report_file_path):
            reason_for_failure = open(
                os.path.join(path_to_logs, pytest_hash, "test_output.txt")
            ).read()
            pytest_info[testname]["failed_to_run"] = reason_for_failure
            return pytest_info
        pytest_report = json.load(open(report_file_path))
        pytest_summary = pytest_report["summary"]
        pytest_info[testname]["summary"] = pytest_summary
        pytest_info[testname]["duration"] = pytest_report["duration"]
        if "passed" not in pytest_summary:
            pytest_summary["passed"] = 0
        for test in pytest_report["tests"]:
            if test["outcome"] == "passed":
                continue
            if "longrepr" in test:
                failure_string = test["longrepr"]
            elif "???" in test:
                failure_string = test["???"]["longrepr"]
            elif test["outcome"] == "error":
                failure_string = test["setup"]["longrepr"]
            elif "setup" in test and "longrepr" in test["setup"]:
                failure_string = test["setup"]["longrepr"]
            elif "call" in test and "longrepr" in test["call"]:
                failure_string = test["call"]["longrepr"]
                # could use test['call']['traceback'] information and test['call']['crash'] for more info
            else:
                failure_string = ""
            duration = 0.0
            for action_key in ["setup", "call", "teardown"]:
                if action_key not in test:
                    continue
                if "duration" in test:
                    duration += test["duration"]
            pytest_info[testname]["failures"][test["nodeid"]] = {
                "failure_string": failure_string,
                "duration": duration,
            }
    return pytest_info


def get_coverage_info(path_to_logs, repo_name, branch_name):
    # coverage_fp = open(os.path.join(path_to_logs, pytest_hash, "coverage.json"))
    # for filename, file_coverage in json.load(coverage_fp)["files"].items():
    #     if not any(relevant_function.startswith(filename) for relevant_function in relevant_functions):
    #         continue
    #     for funcname, func_coverage in file_coverage["functions"].items():
    #         if f"{filename}::{funcname}" not in relevant_functions: continue
    #         pycov_info[testname][f"{filename}::{funcname}"] = {
    #                 "implementation": submission_info["function_impls"][f"{filename}::{funcname}"],
    #                 "executed_lines": func_coverage["executed_lines"],
    #                 "executed_branches": func_coverage["executed_branches"]
    #         }
    raise NotImplementedError


def get_blank_repo_metrics(
    blank_source_code_folder,
    spec_filename,
    tokenizer,
    code_file_filter=lambda filename: filename,
):
    blank_repo_metrics = {
        "functions_to_edit": [],
    }

    for subdir, _, files in os.walk(blank_source_code_folder):
        for file in files:
            if not code_file_filter(file):
                continue
            filename = os.path.join(subdir, file)
            splitted = filename.split("/")
            hidden = False
            for one in splitted:
                if one.startswith("."):
                    hidden = True
                    break
            if hidden:
                continue
            try:
                code = open(filename, encoding="utf-8").read()
            except Exception as e:
                print(f"{e}: Trouble opening {filename}")
                continue

            filename = filename[len(blank_source_code_folder):].lstrip(" /")
            try:
                code_tree = ast.parse(code)
            except Exception as e:
                print(
                    f"{e}: Trouble parsing {os.path.join(blank_source_code_folder, filename)}"
                )
                continue
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
                        blank_repo_metrics["functions_to_edit"].append(
                            f"{filename}::{node.parent_function}"
                        )
                    elif hasattr(node, "parent_class"):
                        blank_repo_metrics["functions_to_edit"].append(
                            f"{filename}::{node.parent_class}"
                        )

    # Get spec metrics
    concatted_spec = ""
    reader = pypdf.PdfReader(spec_filename)
    for p_idx, page in enumerate(reader.pages):
        try:
            concatted_spec += page.extract_text()
        except pypdf.errors.PdfReadError as e:
            print(f"{e}: Could not load page {p_idx} of {spec_filename}, excluding...")
    blank_repo_metrics["no_tokens_in_spec"] = tokenizer(
        concatted_spec, return_tensors="pt"
    ).input_ids.shape[-1]

    return blank_repo_metrics


# def render_leaderboard(split):
    
#     for branch_name, branch_info in all_submissions.items():
#         if branch_info['split'] != split: continue
#         repos_resolved = 0
#         cum_passed = 0
#         total_duration = 0.0
#         for repo_name, repo_test_info in branch_info.items():
#             for testname, test_info in repo_test_info.items():
#                 if "failed_to_run" not in test_info:
#                     total_duration += test_info["duration"]
#                     if ('failed' not in test_info['summary']) or (test_info['summary']['failed'] == 0): 
#                         repos_resolved += 1
#                         # f"{test_info['summary']['collected']} ; duration: {test_info['duration']:.2f}s"
#                     cum_passed += test_info["summary"]["passed"]
#                 break  # assume we ran all tests. will add functionality for checking diff tests later, as we need it.
#         analysis_link = f"[Analysis]({f'analysis_{branch_name}'})"
#         leaderboard += f"\n||[{branch_info['display_name']}]({branch_info['project_page']})|" \
#                        f"{repos_resolved}|" \
#                        f"{cum_passed}|" \
#                        f"{total_duration:.2f}" \
#                        f"{branch_info['submission_date']}|" \
#                        f"{analysis_link}||"
#     return leaderboard


def render_mds(subfolder="docs"):
    leaderboard = {}
    leaderboard["lite"] = f"## Leaderboard (Lite)\n\n"
    leaderboard["all"] = f"## Leaderboard (All)\n\n"

    for split in tqdm.tqdm(["lite", "all"]):
        total_num_repos = 0
        total_num_tests = 0
        for repo_name in SPLIT[split]:
            total_num_repos += 1
            all_tests = subprocess.run(["commit0", "get-tests", repo_name],  capture_output=True, text=True)
            total_num_tests += len(all_tests.stdout.strip().splitlines())
        leaderboard[split] += f"""
|  | Name | Repos Resolved /{total_num_repos} | Net Pass Rate /{total_num_tests} | Test Duration (s) | Date | Analysis | |
|--|------|-----------|------|----------|------|---|--------| |"""

    for branch_name in tqdm.tqdm(glob.glob(os.path.join(analysis_files_path, "*"))):
        branch_name = os.path.basename(branch_name)
        if branch_name in {"blank", "repos", "submission_repos"}:
            continue
        submission_page = """# Submission Name: REPLACE_NAME_HERE (REPLACE_SPLIT_HERE)

| | Repository | Resolved | Pass Rate | Test Duration (s) | Analysis | |
|-|------------|---------|-----| -----|-----||"""
        repos_resolved = 0
        cum_passed = 0
        total_duration = 0.
        for repo_file in glob.glob(
            os.path.join(analysis_files_path, branch_name, "*.json")
        ):
            repo_metrics_output_file = os.path.join(
                analysis_files_path, branch_name, repo_file
            )
            repo_metrics = json.load(open(repo_metrics_output_file))
            repo_name = os.path.basename(repo_file[: -len(".json")])
            submission_repo_page = f"# Submission Name: {branch_name}\n# Repository: {repo_name}"
            if "split" not in locals():
                split = repo_metrics["submission_info"]["split"]
                project_page_link = repo_metrics["submission_info"]["project_page"]
                display_name = repo_metrics["submission_info"]["display_name"]
                submission_date = repo_metrics["submission_info"]['submission_date']
                submission_page = submission_page.replace("REPLACE_NAME_HERE", display_name).replace("REPLACE_SPLIT_HERE", split)
            for pytest_group, pytest_info in repo_metrics.items():
                if pytest_group == "submission_info": continue
                pytest_group = os.path.basename(pytest_group.strip("/"))
                patch_diff = (
                    f"""\n\n### Patch diff\n```diff\n{pytest_info['patch_diff']}```"""
                )
                if "failed_to_run" in pytest_info:
                    submission_repo_page += f"""\n## Failed to run pytests\n```\n{pytest_info['failed_to_run']}\n```"""
                else:
                    submission_repo_page += f"""\n## Pytest Summary: {pytest_group}
| status   | count |
|:---------|:-----:|
"""
                    total_duration += pytest_info["duration"]
                    cum_passed += pytest_info["summary"]["passed"]
                    for category, count in pytest_info["summary"].items():
                        if category not in {"duration"}:
                            submission_repo_page += f"""| {category} | {count} |\n"""
                        else:
                            submission_repo_page += f"""| {category} | {float(count):.2f}s |\n"""

                    submission_repo_page += f"\n## Failed pytest outputs: {pytest_group}\n\n"
                    for testname, failure in pytest_info["failures"].items():
                        shortened_testname = os.path.basename(testname)
                        submission_repo_page += (
                            f"### {shortened_testname}\n\n<details><summary> <pre>{shortened_testname}"
                            f"</pre></summary><pre>\n{failure['failure_string']}\n</pre>\n</details>\n"
                        )
            back_button = f"[back to {branch_name} summary]({f'analysis_{branch_name}'})\n\n"
            with open(
                os.path.join(subfolder, f"analysis_{branch_name}_{repo_name}.md"), "w"
            ) as wf:
                wf.write(
                    back_button
                    + submission_repo_page
                    + patch_diff
                )
            resolved = ('summary' in pytest_info) and (('failed' not in pytest_info['summary']) or (pytest_info['summary']['failed'] == 0))
            if resolved: repos_resolved += 1
            pytest_details = "Pytest failed" if "failed_to_run" in pytest_info else f"{pytest_info['summary']['passed']} / {pytest_info['summary']['collected']}"
            duration = "Failed."
            if 'duration' in pytest_info: duration = f"{pytest_info['duration']:.2f}"
            submission_page +=f"""
| | {repo_name} | {'Yes' if resolved else 'No'} | {pytest_details} | {duration} | {f'analysis_{branch_name}_{repo_name}'} | |"""
        analysis_link = f"[Analysis]({f'analysis_{branch_name}'})"
        leaderboard[split] += f"\n||[{display_name}]({project_page_link})|" \
                    f"{repos_resolved}|" \
                    f"{cum_passed}|" \
                    f"{total_duration:.2f}" \
                    f"{submission_date}|" \
                    f"{analysis_link}||"


        back_button = f"[back to all submissions]({f'analysis'})\n\n"
        with open(os.path.join(subfolder, f"analysis_{branch_name}.md"), "w") as wf:
            wf.write(back_button + "\n" + submission_page)

    with open(os.path.join(subfolder, "analysis.md"), "w") as wf:
        wf.write(leaderboard["lite"] + leaderboard["all"])


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--do_setup", action="store_true")
    parser.add_argument("--get_blank_details", action="store_true")
    parser.add_argument("--get_reference_details", action="store_true")
    parser.add_argument("--keep_previous_eval", action="store_true")
    parser.add_argument("--analyze_submissions", action="store_true")
    parser.add_argument("--render_webpages", action="store_true")

    parser.add_argument("--split", type=str, default="lite")

    parser.add_argument(
        "--tokenizer_name", type=str, default="meta-llama/Meta-Llama-3.1-8B-Instruct"
    )

    return parser.parse_args()


def main(args):
    global analysis_files_path

    commit0_dataset_name = "wentingzhao/commit0_combined"
    submissions_dataset_name = "celinelee/commit0_submissions"
    dataset = load_dataset(commit0_dataset_name, split="test")  # type: ignore
    submission_dataset = load_dataset(submissions_dataset_name, split="train")

    if args.get_blank_details:
        if args.do_setup:
            os.system(
                f"commit0 setup {args.split} --base-dir {analysis_files_path}/repos "
                f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
            )
        branch_name = "blank"
        if not args.keep_previous_eval:
            if os.path.exists(os.path.join(analysis_files_path, branch_name)):
                shutil.rmtree(os.path.join(analysis_files_path, branch_name))
        os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name)
        for example in dataset:
            repo_name = example["repo"].split("/")[-1]
            if args.split != "all" and repo_name not in SPLIT[args.split]:
                continue

            repo_metrics_output_file = os.path.join(
                analysis_files_path, branch_name, f"{repo_name}.json"
            )
            blank_source_code_folder = os.path.join(
                analysis_files_path, "repos", repo_name, example["src_dir"]
            )
            spec_filepath = os.path.join(
                analysis_files_path, "repos", repo_name, "spec.pdf"
            )

            repo_metrics = get_blank_repo_metrics(
                blank_source_code_folder,
                spec_filepath,
                tokenizer,
                code_file_filter=lambda filename: re.fullmatch(r".*\.py", filename)
                is not None,
            )
            json.dump(repo_metrics, open(repo_metrics_output_file, "w"), indent=4)

    if args.get_reference_details:
        if args.do_setup:
            os.system(
                f"commit0 setup {args.split} --base-dir {analysis_files_path}/repos "
                f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
            )
        branch_name = "reference"
        os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
        if not args.keep_previous_eval:
            for repo_log_path in glob.glob(f"{os.getcwd()}/logs/pytest/*"):
                if os.path.exists(os.path.join(repo_log_path, branch_name)):
                    shutil.rmtree(os.path.join(repo_log_path, branch_name))
        os.system(
            "commit0 evaluate --reference "
            f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
        )

        # get coverage and pytest info for each repo
        for example in dataset:
            repo_name = example["repo"].split("/")[-1]
            if args.split != "all" and repo_name not in SPLIT[args.split]:
                continue

            repo_metrics_output_file = os.path.join(
                analysis_files_path, branch_name, f"{repo_name}.json"
            )

            path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
            pytest_results = get_pytest_info(path_to_logs, repo_name, branch_name)
            pytest_results["submission_info"] = example
            json.dump(pytest_results, open(repo_metrics_output_file, "w"), indent=4)

    if args.analyze_submissions:
        commit0_dot_file_path = os.path.join(
            analysis_files_path, "submission_repos", ".commit0.yaml"
        )
        if not args.keep_previous_eval:
            for subfolder in glob.glob(os.path.join(analysis_files_path, "*")):
                if os.path.basename(subfolder.rstrip("/")) not in {"blank", "reference", "repos", "submission_repos"}:
                    try:
                        print(f"Clearing {subfolder}")
                        shutil.rmtree(subfolder)
                    except Exception as e:
                        print(f"{e}: when removing {subfolder}")

        for submission in submission_dataset:
            branch_name = submission["branch"]
            os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
            if not args.keep_previous_eval:
                for repo_log_path in glob.glob(f"{os.getcwd()}/logs/pytest/*"):
                    if os.path.exists(os.path.join(repo_log_path, branch_name)):
                        shutil.rmtree(os.path.join(repo_log_path, branch_name))
            for example in dataset:
                repo_name = example["repo"].split("/")[-1]
                if args.split != "all" and repo_name not in SPLIT[args.split]:
                    continue
                clone_url = f"https://github.com/test-save-commit0/{repo_name}.git"
                clone_dir = os.path.abspath(
                    os.path.join(analysis_files_path, "submission_repos", repo_name)
                )
                clone_repo(clone_url, clone_dir, branch_name, logger)
            # after successfully setup, write the commit0 dot file
            write_commit0_dot_file(
                commit0_dot_file_path,
                {
                    "dataset_name": commit0_dataset_name,
                    "dataset_split": "test",
                    "repo_split": args.split,
                    "base_dir": os.path.join(analysis_files_path, "submission_repos"),
                },
            )
            # run pytests
            os.system(
                f"commit0 evaluate --branch {branch_name} "
                f"--commit0-dot-file-path {commit0_dot_file_path}"
            )
            for example in dataset:
                repo_name = example["repo"].split("/")[-1]
                if args.split != "all" and repo_name not in SPLIT[args.split]:
                    continue

                repo_metrics_output_file = os.path.join(
                    analysis_files_path, branch_name, f"{repo_name}.json"
                )

                path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
                pytest_results = get_pytest_info(path_to_logs, repo_name, branch_name)
                json.dump(pytest_results, open(repo_metrics_output_file, "w"), indent=4)

    if not args.keep_previous_eval:
        for analysis_file in glob.glob("docs/analysis*.md"):
            os.unlink(analysis_file)
    if args.render_webpages:
        render_mds()


main(get_args())
