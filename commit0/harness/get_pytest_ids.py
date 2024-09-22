import bz2
from typing import List


def main(repo: str, verbose: int) -> List[str]:
    repo = repo.lower()
    repo = repo.replace(".", "-")
    with bz2.open(f"commit0/data/test_ids/{repo}.bz2", 'rt') as f:
        out = f.read()
    out = out.split("\n")
    return out


__all__ = []
