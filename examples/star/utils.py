import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import Dataset
from tqdm import tqdm
from typing import List, Tuple


def execute_tests(
    examples: Dataset, all_samples: List[List[str]], max_workers: int = 100
) -> Tuple[List[List[str]], List[List[int]]]:
    """Run `commit0 test` in parallel for all (example, sample) pairs and collect results.

    This function:
    1. Flattens the iteration over examples and samples into a single list of tasks.
    2. Executes them in parallel with a ThreadPoolExecutor.
    3. Reassembles the results into two lists of lists:
       - `all_traces`, containing the stdout for each sample.
       - `all_execution_results`, containing the exit code for each sample.

    We assume:
    - `ds["train"]` is a list of dictionaries, each representing an example.
      Each example contains an "instance_id" key.
    - `all_samples` is a list where each element corresponds to an example from `ds["train"]`.
      Each element of `all_samples` is a list of strings (samples).
    - All elements of `all_samples` are of equal length.

    Args:
    ----
        ds (Dataset): A Dataset object.
        all_samples (List[List[str]]): A 2D list of strings, where `all_samples[i]` corresponds to the samples associated with `ds[i]`.
        max_workers (int): The number of worker threads to use for parallel execution. Default is 100.

    Returns:
    -------
        Tuple[List[List[str]], List[List[int]]]:
            A tuple of (all_traces, all_execution_results) where:
            - all_traces is a 2D list of strings: all_traces[i][j] is the stdout from running `commit0 test` on `ds[i]` with `all_samples[i][j]` as stdin.
            - all_execution_results is a 2D list of ints: all_execution_results[i][j] is the exit code from running the command for that example/sample pair.

    """
    M = len(examples)
    N = len(all_samples[0]) if M > 0 else 0

    # Flatten tasks: each task is (example_index, sample_index, instance_id, input_sample)
    tasks = []
    for i, example in enumerate(examples):
        instance_id = str(example["instance_id"])
        for j, sample in enumerate(all_samples[i]):
            tasks.append((i, j, instance_id, sample))

    all_traces = [[None] * N for _ in range(M)]
    all_execution_results = [[None] * N for _ in range(M)]

    # Run all tasks in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                subprocess.run,
                ["commit0", "test", instance_id, "--timeout", "30", "--stdin"],
                input=sample,
                text=True,
                capture_output=True,
            ): (i, j)
            for (i, j, instance_id, sample) in tasks
        }

        for future in tqdm(
            as_completed(futures), total=len(tasks), desc="Executing tests"
        ):
            i, j = futures[future]
            result = future.result()
            stdout = result.stdout
            exit_code = result.returncode
            all_traces[i][j] = stdout
            all_execution_results[i][j] = exit_code

    return all_traces, all_execution_results


def generate_prompt(prompt: str, test: str) -> str:
    """
    Generate a Python code request prompt string.
    """
    return f"""Write a Python function implementation for the following prompt:

{prompt}

Your code should satisfy these tests:

{test}

Return only the implementation code, no tests or explanations. Be sure to include the relevant import statements:
```python
code
```
"""
