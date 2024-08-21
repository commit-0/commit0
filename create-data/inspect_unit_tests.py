import sys
import numpy as np

from collections import Counter
from datasets import load_dataset

dataset = load_dataset("json", data_files=sys.argv[1], split="train")
for example in dataset:
    status = Counter([x["status"] for x in example["report"]])
    runtimes = [float(x["time"]) for x in example["report"]]
    mean = np.mean(runtimes) / 60
    std = np.std(runtimes) / 60
    total = np.sum(runtimes) / 60
    print(example["name"], f"{total:4f} {mean:4f} +- {std:4f}", status)
