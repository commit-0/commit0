from typing import Any, Dict, Union

from pydantic import BaseModel


class Commit0Config(BaseModel):
    base_dir: str
    dataset_name: str
    repo_split: str


class AiderConfig(BaseModel):
    llm_name: str
    use_repo_info: bool
    max_repo_info_length: int
    use_unit_tests_info: bool
    max_unit_tests_info_length: int
    use_reference_info: bool
    max_reference_info_length: int
    use_lint_info: bool
    max_lint_info_length: int


class BaselineConfig(BaseModel):
    config: Dict[str, Dict[str, Union[str, bool, int]]]

    commit0_config: Commit0Config | None = None
    aider_config: AiderConfig | None = None

    def model_post_init(self, __context: Any) -> None:
        """Post-initialize the model."""
        self.commit0_config = Commit0Config(**self.config["commit0_config"])
        self.aider_config = AiderConfig(**self.config["aider_config"])
