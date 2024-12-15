"""Main STaR Loop"""

from copy import deepcopy
from datasets import Dataset, DatasetDict, load_dataset
from inference import generate_predictions
from train import train
from utils import execute_tests, format_solution, generate_prompt, parse_args


def main():
    args = parse_args()
    ds = load_dataset(args.dataset_name, args.dataset_config_name)
    assert "train" in ds
    # format the dataset for training and evaluation
    for split in ds:
        texts = []
        if split == "train": continue
        for example in ds[split]:
            canonical_solution = f"```python\n{example['canonical_solution']}\n```"
            text = [{"role": "user", "message": generate_prompt(example["prompt"], example["test"])}, {"role": "assistant", "message": format_solution(canonical_solution, example["prompt"])}]
            texts.append(text)
        ds[split] = ds[split].add_column(name="text", column=texts)

    model_name = args.model_name_or_path
    output_dir = deepcopy(args.output_dir)
    for i in range(args.iteration):
        # sample
        all_samples = generate_predictions(
            model_name, ds["train"], args.temperature, args.n
        )
        ds["train"].add_column(name="sample", column=all_samples).to_json(f"{output_dir}/data/samples-iter{i}.json")
        assert len(ds["train"]) == len(all_samples)

        # verify and construct the training set
        all_traces, all_execution_results = execute_tests(ds["train"], all_samples, max_workers=args.max_workers)
        passed_examples = []
        for example, execution_results, samples in zip(
            ds["train"], all_execution_results, all_samples
        ):
            for execution_result, sample in zip(execution_results, samples):
                # pytest exit code: https://docs.pytest.org/en/stable/reference/exit-codes.html
                if execution_result == 0:
                    example["text"] = [{"role": "user", "message": generate_prompt(example["prompt"], example["test"])}, {"role": "assistant", "message": format_solution(sample, example["prompt"])}]
                    passed_examples.append(example)
                    break
        raw_datasets = DatasetDict({"train": Dataset.from_list(passed_examples), "validation": ds["validation"]})
        raw_datasets["train"].to_json(f"{output_dir}/data/verified-samples-iter{i}.json")

        # train
        args.output_dir = f"{output_dir}/models-iter{i}"
        train(raw_datasets, model_name, args)
        model_name = args.output_dir


if __name__ == "__main__":
    main()
