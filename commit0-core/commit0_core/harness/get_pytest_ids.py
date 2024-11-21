import bz2
from typing import List
import commit0
import os


def main(repo: str, verbose: int) -> List[str]:
    repo = repo.lower()
    repo = repo.replace(".", "-")
    commit0_path = os.path.dirname(commit0.__file__)
    bz2_file = f"{commit0_path}/data/test_ids/{repo}.bz2"
    with bz2.open(bz2_file, "rt") as f:
        out = f.read()
    if verbose:
        print(out)
    out = out.split("\n")
    return out


__all__ = []
