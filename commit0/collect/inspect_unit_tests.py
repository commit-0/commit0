import sys
import numpy as np

from collections import Counter
from datasets import load_dataset

dataset = load_dataset("json", data_files=sys.argv[1], split="train")
out = []
for example in dataset:
    status = Counter([x["status"] for x in example["report"]])
    runtimes = [float(x["time"]) for x in example["report"]]
    if len(runtimes) == 0:
        mean, std, total, passed = 0, 0, 0, 0
    else:
        mean = np.mean(runtimes) / 60
        std = np.std(runtimes) / 60
        total = np.sum(runtimes) / 60
        if "xfail" not in status:
            status["xfail"] = 0
        passed = (status["passed"] + status["xfail"]) / sum(status.values())
    out.append(
        {
            "name": example["name"],
            "sum": total,
            "mean": mean,
            "std": std,
            "passed": passed,
        }
    )
out = sorted(out, key=lambda x: x["sum"], reverse=True)
for x in out:
    print(
        f"{x['name'].split('/')[1]},{x['sum']:4f},{x['mean']:4f},{x['std']:4f},{x['passed']}"
    )
