import logging
import os
from collections import Counter

from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import load_dataset
from tqdm import tqdm
from typing import Iterator, Union

from commit0.harness.run_pytest_ids import main as run_tests
from commit0.harness.get_pytest_ids import main as get_tests
from commit0.harness.constants import RepoInstance, SPLIT, RUN_PYTEST_LOG_DIR
from commit0.harness.utils import get_hash_string, get_active_branch

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(
    dataset_name: str,
    dataset_split: str,
    repo_split: str,
    base_dir: str,
    branch: Union[str, None],
    coverage: bool,
    backend: str,
    timeout: int,
    num_cpus: int,
    num_workers: int,
    rebuild_image: bool,
) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    repos = SPLIT[repo_split]
    triples = []
    log_dirs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        hashed_test_ids = get_hash_string(example["test"]["test_dir"])
        if branch is None:
            git_path = os.path.join(base_dir, repo_name)
            branch = get_active_branch(git_path)
        log_dir = RUN_PYTEST_LOG_DIR / repo_name / branch / hashed_test_ids
        log_dirs.append(str(log_dir))
        triples.append((repo_name, example["test"]["test_dir"], branch))

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
                    coverage,
                    backend,
                    timeout,
                    num_cpus,
                    rebuild_image=rebuild_image,
                    verbose=0,
                ): None
                for repo, test_dir, branch in triples
            }
            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)

    # get numbers
    out = []
    for name in tqdm(log_dirs):
        report_file = os.path.join(name, "report.json")
        name = name.split("/")[2]
        test_ids = get_tests(name, verbose=0)
        if not os.path.exists(report_file):
            out.append(
                {
                    "name": name,
                    "sum": 0,
                    "passed": 0,
                    "num_passed": 0,
                    "num_tests": len(test_ids),
                }
            )
            continue
        report = load_dataset("json", data_files=report_file, split="train")  # type: ignore
        tests = {x["nodeid"]: x["call"] for x in report["tests"][0] if "call" in x}  # type: ignore
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
                "num_tests": len(test_ids),
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
