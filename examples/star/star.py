"""Main STaR Loop"""
import argparse
from datasets import Dataset, load_dataset
from inference import generate_predictions

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, required=True, help="model to use")
    parser.add_argument("--dataset_name", type=str, required=True, help="dataset to use")
    parser.add_argument("--temperature", type=float, default=1)
    parser.add_argument("-n", type=int, default=1)
    args = parser.parse_args()

    ds = load_dataset(args.dataset_name)
    assert "train" in ds
    samples = generate_predictions(args.model_name, ds["train"], args.temperature, args.n)

if __name__ == '__main__':
    main()
