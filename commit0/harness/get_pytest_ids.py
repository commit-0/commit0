import bz2
from typing import List
import commit0
import os


def read(bz2_file: str) -> str:
    with bz2.open(bz2_file, "rt") as f:
        out = f.read()
    return out


def main(repo: str, verbose: int) -> List[List[str]]:
    repo = repo.lower()
    repo = repo.replace(".", "-")
    commit0_path = os.path.dirname(commit0.__file__)
    if "__" in repo:
        in_file_fail = read(f"{commit0_path}/data/test_ids/{repo}#fail_to_pass.bz2")
        in_file_pass = read(f"{commit0_path}/data/test_ids/{repo}#pass_to_pass.bz2")
    else:
        in_file_fail = read(f"{commit0_path}/data/test_ids/{repo}.bz2")
        in_file_pass = ""
    out = [in_file_fail, in_file_pass]
    if verbose:
        print(f"{out[0]}\n{out[1]}")
    out = [out[0].split("\n"), out[1].split("\n")]
    return out


__all__ = []
