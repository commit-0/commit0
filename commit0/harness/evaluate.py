import logging
import os
import traceback
from collections import Counter

from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import load_dataset
from tqdm import tqdm
from typing import Iterator

from commit0.harness.run_pytest_ids import main as run_tests
from commit0.harness.get_pytest_ids import main as get_tests
from commit0.harness.constants import RepoInstance, SPLIT

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    dataset_name: str,
    dataset_split: str,
    repo_split: str,
    base_dir: str,
    branch: str,
    backend: str,
    timeout: int,
    num_workers: int,
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    repos = SPLIT[repo_split]
    pairs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        pairs.append((repo_name, example["test"]["test_dir"]))

    log_dirs = []
    with tqdm(total=len(repos), smoothing=0, desc="Evaluating repos") as pbar:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Create a future for running each instance
            futures = {
                executor.submit(
                    run_tests,
                    dataset_name,
                    dataset_split,
                    base_dir,
                    repo,
                    branch,
                    test_dir,
                    backend,
                    timeout,
                    stdout=False,
                ): None
                for repo, test_dir in pairs
            }
            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    # Update progress bar, check if instance ran successfully
                    result = future.result()
                    log_dirs.append(result)
                except Exception:
                    traceback.print_exc()
                    continue

    # get numbers
    out = []
    for name in tqdm(log_dirs):
        report_file = os.path.join(name, "report.json")
        name = name.split("/")[2]
        if not os.path.exists(report_file):
            out.append(
                {
                    "name": name,
                    "sum": 0,
                    "passed": 0,
                    "num_passed": 0,
                }
            )
            continue
        report = load_dataset("json", data_files=report_file, split="train")  # type: ignore
        test_ids = get_tests(name, stdout=False)
        tests = {x["nodeid"]: x["call"] for x in report["tests"][0]}  # type: ignore
        status = []
        runtimes = []
        no_runs = 0
        for test_id in test_ids:
            if test_id in tests and tests[test_id] is not None:
                status.append(tests[test_id]["outcome"])
                runtimes.append(tests[test_id]["duration"])
                no_runs += 1
            else:
                status.append("failed")
                runtimes.append(0)
        status = Counter(status)
        if no_runs == 0:
            total = 0
        else:
            total = sum(runtimes)
        if "xfail" not in status:
            status["xfail"] = 0
        passed = (status["passed"] + status["xfail"]) / sum(status.values())
        out.append(
            {
                "name": name,
                "sum": total,
                "passed": passed,
                "num_passed": status["passed"] + status["xfail"],
                "num_tests": sum(status.values()),
            }
        )
    print("repo,runtime,num_passed/num_tests")
    out = sorted(out, key=lambda x: x["sum"], reverse=True)
    for x in out:
        print(f"{x['name']},{x['sum']},{x['num_passed']}/{x['num_tests']}")
    total_runtime = sum([x["sum"] for x in out])
    averaged_passed = sum([x["passed"] for x in out]) / len(out)
    print(f"total runtime: {total_runtime}")
    print(f"average pass rate: {averaged_passed}")


__all__ = []
