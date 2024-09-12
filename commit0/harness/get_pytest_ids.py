import tarfile
from typing import List


def main(repo: str, stdout: bool) -> List[str]:
    repo = repo.lower()
    repo = repo.replace(".", "-")
    out = ""
    with tarfile.open(f"commit0/data/test_ids/{repo}.tar.bz2", "r:bz2") as tar:
        for member in tar.getmembers():
            if member.isfile():
                file = tar.extractfile(member)
                if file:
                    content = file.read().decode("utf-8")
                    out += content
                    if stdout:
                        print(content)
    out = out.split("\n")
    return out


__all__ = []
