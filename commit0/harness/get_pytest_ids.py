import tarfile


def main(repo: str) -> None:
    repo = repo.lower()
    repo = repo.replace(".", "-")
    with tarfile.open(f"commit0/data/test_ids/{repo}.tar.bz2", "r:bz2") as tar:
        for member in tar.getmembers():
            if member.isfile():
                file = tar.extractfile(member)
                if file:
                    content = file.read()
                    print(content.decode("utf-8"))


__all__ = []
