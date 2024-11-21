from dataclasses import dataclass


@dataclass
class AgentConfig:
    agent_name: str
    model_name: str
    use_user_prompt: bool
    user_prompt: str
    use_topo_sort_dependencies: bool
    add_import_module_to_context: bool
    use_repo_info: bool
    max_repo_info_length: int
    use_unit_tests_info: bool
    max_unit_tests_info_length: int
    use_spec_info: bool
    max_spec_info_length: int
    use_lint_info: bool
    run_entire_dir_lint: bool
    max_lint_info_length: int
    pre_commit_config_path: str
    run_tests: bool
    max_iteration: int
    record_test_for_each_commit: bool
