import logging

import docker
from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import load_dataset
from tqdm import tqdm
from typing import Iterator

from commit0.harness.run_pytest_ids import main as run_tests
from commit0.harness.constants import RepoInstance, SPLIT

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(dataset_name: str, dataset_split: str, repo_split: str, base_dir: str, branch: str, backend: str, timeout: int, num_workers: int) -> None:
    dataset: Iterator[RepoInstance] = load_dataset(dataset_name, split=dataset_split)  # type: ignore
    repos = SPLIT[repo_split]
    test_dirs = []
    for example in dataset:
        repo_name = example["repo"].split("/")[-1]
        if repo_split != "all" and repo_name not in SPLIT[repo_split]:
            continue
        test_dirs.append(example["test"]["test_dir"])

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
                for repo, test_dir in zip(repos, test_dirs)
            }
            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    # Update progress bar, check if instance ran successfully
                    result = future.result()
                    log_dirs.append(result)
                except Exception as e:
                    traceback.print_exc()
                    continue


__all__ = []
