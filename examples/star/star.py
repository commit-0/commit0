"""Main STaR Loop"""

import argparse
from datasets import Dataset, load_dataset
from inference import generate_predictions
from utils import execute_tests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, required=True, help="model to use")
    parser.add_argument(
        "--dataset_name", type=str, required=True, help="dataset to use"
    )
    parser.add_argument("--temperature", type=float, default=1)
    parser.add_argument("-n", type=int, default=1)
    args = parser.parse_args()

    ds = load_dataset(args.dataset_name)
    assert "train" in ds
    all_samples = generate_predictions(
        args.model_name, ds["train"], args.temperature, args.n
    )
    assert len(ds["train"]) == len(all_samples)
    all_traces, all_execution_results = execute_tests(ds["train"], all_samples)
    passed_examples = []
    for example, execution_results, samples in zip(
        ds["train"], all_execution_results, all_samples
    ):
        for execution_result, sample in zip(execution_results, samples):
            if execution_result == 0:
                example["prediction"] = sample
                passed_examples.append(example)
                break
    new_ds = Dataset.from_list(passed_examples)
    new_ds.to_json("star_training.json")
    print(len(passed_examples) / len(ds["train"]))


if __name__ == "__main__":
    main()
