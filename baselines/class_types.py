from dataclasses import dataclass


@dataclass
class Commit0Config:
    base_dir: str
    dataset_name: str
    dataset_split: str
    repo_split: str
    num_workers: int


@dataclass
class AiderConfig:
    llm_name: str
    use_user_prompt: bool
    user_prompt: str
    use_repo_info: bool
    max_repo_info_length: int
    use_unit_tests_info: bool
    max_unit_tests_info_length: int
    use_reference_info: bool
    max_reference_info_length: int
    use_lint_info: bool
    max_lint_info_length: int
    pre_commit_config_path: str
    run_tests: bool