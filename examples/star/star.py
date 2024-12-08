"""Main STaR Loop"""

from datasets import Dataset, load_dataset
from inference import generate_predictions
from train import train
from utils import execute_tests, parse_args


def main():
    args = parse_args()
    ds = load_dataset(args.dataset_name)
    assert "train" in ds
    all_samples = generate_predictions(
        args.model_name_or_path, ds["train"], args.temperature, args.n
    )
    assert len(ds["train"]) == len(all_samples)
    all_traces, all_execution_results = execute_tests(ds["train"], all_samples)
    passed_examples = []
    for example, execution_results, samples in zip(
        ds["train"], all_execution_results, all_samples
    ):
        for execution_result, sample in zip(execution_results, samples):
            # pytest exit code: https://docs.pytest.org/en/stable/reference/exit-codes.html
            if execution_result == 0:
                example["prediction"] = sample
                passed_examples.append(example)
                break
    new_ds = Dataset.from_list(passed_examples)
    new_ds.to_json("star_training.json")
    print(len(passed_examples) / len(ds["train"]))
    train(args)


if __name__ == "__main__":
    main()
