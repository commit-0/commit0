from dataclasses import dataclass


@dataclass
class Commit0Config:
    # shared in all steps
    dataset_name: str
    dataset_split: str

    # clone related
    base_dir: str

    # build related
    # which repo to build, all or one repo
    build: str
    num_workers: int

    # test related
    backend: str
    # which branch to work on
    branch: str
    # timeout for running pytest
    timeout: int
