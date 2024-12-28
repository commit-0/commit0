"""Get test accuracy"""

from datasets import load_dataset
from examples.star.inference import generate_predictions
from examples.star.utils import (
    execute_tests,
    generate_prompt,
    parse_args,
)


def main() -> None:
    args = parse_args()
    ds = load_dataset(args.dataset_name, args.dataset_config_name)['test']
    model_name = args.model_name_or_path

    # sample
    all_samples = generate_predictions(
        model_name, ds, args.temperature, args.n
    )
    ds.add_column(name="sample", column=all_samples).to_json(
        f"{args.output_dir}/data/{model_name.split('/')[-1]}-test-samples.json"
    )
    assert len(ds) == len(all_samples)

    # verify and construct the training set
    all_traces, all_execution_results = execute_tests(
        ds, all_samples, max_workers=args.max_workers
    )
    passed = 0
    for example, execution_results, samples in zip(
        ds, all_execution_results, all_samples
    ):
        for execution_result, sample in zip(execution_results, samples):
            # pytest exit code: https://docs.pytest.org/en/stable/reference/exit-codes.html
            if execution_result == 0:
                passed += 1
    print(f"passed: {passed/len(ds)}")

if __name__ == "__main__":
    main()


__all__ = []
