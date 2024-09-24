from dataclasses import dataclass


@dataclass
class AgentConfig:
    agent_name: str
    model_name: str
    use_user_prompt: bool
    user_prompt: str
    use_repo_info: bool
    max_repo_info_length: int
    use_unit_tests_info: bool
    max_unit_tests_info_length: int
    use_spec_info: bool
    max_spec_info_length: int
    use_lint_info: bool
    max_lint_info_length: int
    pre_commit_config_path: str
    run_tests: bool
    max_iteration: int
