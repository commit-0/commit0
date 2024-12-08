import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import Dataset
from tqdm import tqdm
from typing import List, Tuple
from transformers import MODEL_MAPPING, SchedulerType


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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Finetune a transformers model on a causal language modeling task"
    )
    parser.add_argument("--temperature", type=float, default=1)
    parser.add_argument("-n", type=int, default=1)
    parser.add_argument(
        "--dataset_name",
        type=str,
        default=None,
        help="The name of the dataset to use (via the datasets library).",
    )
    parser.add_argument(
        "--dataset_config_name",
        type=str,
        default=None,
        help="The configuration name of the dataset to use (via the datasets library).",
    )
    parser.add_argument(
        "--model_name_or_path",
        type=str,
        help="Path to pretrained model or model identifier from huggingface.co/models.",
        required=False,
    )
    parser.add_argument(
        "--use_slow_tokenizer",
        action="store_true",
        help="If passed, will use a slow tokenizer (not backed by the 🤗 Tokenizers library).",
    )
    parser.add_argument(
        "--per_device_train_batch_size",
        type=int,
        default=8,
        help="Batch size (per device) for the training dataloader.",
    )
    parser.add_argument(
        "--per_device_eval_batch_size",
        type=int,
        default=8,
        help="Batch size (per device) for the evaluation dataloader.",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=5e-5,
        help="Initial learning rate (after the potential warmup period) to use.",
    )
    parser.add_argument(
        "--weight_decay", type=float, default=0.0, help="Weight decay to use."
    )
    parser.add_argument(
        "--num_train_epochs",
        type=int,
        default=3,
        help="Total number of training epochs to perform.",
    )
    parser.add_argument(
        "--max_train_steps",
        type=int,
        default=None,
        help="Total number of training steps to perform. If provided, overrides num_train_epochs.",
    )
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=1,
        help="Number of updates steps to accumulate before performing a backward/update pass.",
    )
    parser.add_argument(
        "--lr_scheduler_type",
        type=SchedulerType,
        default="linear",
        help="The scheduler type to use.",
        choices=[
            "linear",
            "cosine",
            "cosine_with_restarts",
            "polynomial",
            "constant",
            "constant_with_warmup",
        ],
    )
    parser.add_argument(
        "--num_warmup_steps",
        type=int,
        default=0,
        help="Number of steps for the warmup in the lr scheduler.",
    )
    parser.add_argument(
        "--output_dir", type=str, default=None, help="Where to store the final model."
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="A seed for reproducible training."
    )
    parser.add_argument(
        "--preprocessing_num_workers",
        type=int,
        default=None,
        help="The number of processes to use for the preprocessing.",
    )
    parser.add_argument(
        "--overwrite_cache",
        action="store_true",
        help="Overwrite the cached training and evaluation sets",
    )
    parser.add_argument(
        "--push_to_hub",
        action="store_true",
        help="Whether or not to push the model to the Hub.",
    )
    parser.add_argument(
        "--hub_model_id",
        type=str,
        help="The name of the repository to keep in sync with the local `output_dir`.",
    )
    parser.add_argument(
        "--hub_token", type=str, help="The token to use to push to the Model Hub."
    )
    parser.add_argument(
        "--trust_remote_code",
        action="store_true",
        help=(
            "Whether to trust the execution of code from datasets/models defined on the Hub."
            " This option should only be set to `True` for repositories you trust and in which you have read the"
            " code, as it will execute code present on the Hub on your local machine."
        ),
    )
    parser.add_argument(
        "--checkpointing_steps",
        type=str,
        default=None,
        help="Whether the various states should be saved at the end of every n steps, or 'epoch' for each epoch.",
    )
    parser.add_argument(
        "--with_tracking",
        action="store_true",
        help="Whether to enable experiment trackers for logging.",
    )
    parser.add_argument(
        "--report_to",
        type=str,
        default="all",
        help=(
            'The integration to report the results and logs to. Supported platforms are `"tensorboard"`,'
            ' `"wandb"`, `"comet_ml"` and `"clearml"`. Use `"all"` (default) to report to all integrations. '
            "Only applicable when `--with_tracking` is passed."
        ),
    )
    parser.add_argument(
        "--low_cpu_mem_usage",
        action="store_true",
        help=(
            "It is an option to create the model as an empty shell, then only materialize its parameters when the pretrained weights are loaded. "
            "If passed, LLM loading time and RAM consumption will be benefited."
        ),
    )
    args = parser.parse_args()

    if args.push_to_hub:
        if args.output_dir is None:
            raise ValueError(
                "Need an `output_dir` to create a repo when `--push_to_hub` is passed."
            )

    return args
