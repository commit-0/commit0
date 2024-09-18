from dataclasses import dataclass
from typing import Optional


@dataclass
class Commit0Config:
    # shared in all steps
    dataset_name: str
    dataset_split: str

    # clone related
    base_dir: str
    repo_split: str

    # build related
    # which repo to build, all or one repo
    num_workers: int

    # test related
    backend: str
    # timeout for running pytest
    timeout: int
    num_cpus: int

    # save related
    github_token: Optional[str]
