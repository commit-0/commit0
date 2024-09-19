from enum import Enum
from pathlib import Path
from typing import Dict, TypedDict


class RepoInstance(TypedDict):
    repo: str
    base_commit: str
    reference_commit: str
    setup: dict
    test: Dict[str, str]


class Files(TypedDict):
    eval_script: Dict[str, Path]
    patch: Dict[str, Path]


# Constants - Evaluation Log Directories
BASE_IMAGE_BUILD_DIR = Path("logs/build_images/base")
REPO_IMAGE_BUILD_DIR = Path("logs/build_images/repo")
RUN_PYTEST_LOG_DIR = Path("logs/pytest")
RUN_AIDER_LOG_DIR = Path("logs/aider")

# Constants - Test Types, Statuses, Commands
FAIL_TO_PASS = "FAIL_TO_PASS"
FAIL_TO_FAIL = "FAIL_TO_FAIL"
PASS_TO_PASS = "PASS_TO_PASS"
PASS_TO_FAIL = "PASS_TO_FAIL"

# Evaluation backends
EVAL_BACKENDS = ["local", "modal"]

# available commands
COMMANDS = [
    "clone",
    "build",
    "test",
    "test-reference",
    "get-tests",
    "evaluate",
    "evaluate-reference",
    "lint",
    "save",
]
# repo splits
SPLIT_MINITORCH = ["minitorch"]
SPLIT_SIMPY = ["simpy"]
SPLIT_LITE = [
    "tinydb",
    "simpy",
    "deprecated",
    "wcwidth",
    "voluptuous",
    "cachetools",
    "imapclient",
    "marshmallow",
    "jinja",
    "cookiecutter",
]
SPLIT_ALL = [
    "statsmodels",
    "python-progressbar",
    "xarray",
    "imbalanced-learn",
    "web3.py",
    "scrapy",
    "seaborn",
    "pypdf",
    "pexpect",
    "pytest",
    "pylint",
    "joblib",
    "dulwich",
    "virtualenv",
    "minitorch",
    "networkx",
    "requests",
    "sphinx",
    "jedi",
    "moviepy",
    "loguru",
    "paramiko",
    "geopandas",
    "bitstring",
    "fastapi",
    "chardet",
    "tornado",
    "python-prompt-toolkit",
    "attrs",
    "PyBoy",
    "pydantic",
    "filesystem_spec",
    "tlslite-ng",
    "graphene",
    "mimesis",
    "babel",
    "dnspython",
    "portalocker",
    "cookiecutter",
    "pyjwt",
    "python-rsa",
    "more-itertools",
    "simpy",
    "click",
    "fabric",
    "jinja",
    "flask",
    "sqlparse",
    "marshmallow",
    "imapclient",
    "tinydb",
    "cachetools",
    "voluptuous",
    "parsel",
    "wcwidth",
    "deprecated",
]

SPLIT = {
    "all": SPLIT_ALL,
    "minitorch": SPLIT_MINITORCH,
    "simpy": SPLIT_SIMPY,
    "lite": SPLIT_LITE,
}


class ResolvedStatus(Enum):
    NO = "RESOLVED_NO"
    PARTIAL = "RESOLVED_PARTIAL"
    FULL = "RESOLVED_FULL"


class TestStatus(Enum):
    FAILED = "FAILED"
    PASSED = "PASSED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    XFAIL = "XFAIL"


# Constants - Logging
INSTALL_FAIL = ">>>>> Init Failed"
INSTALL_PASS = ">>>>> Init Succeeded"
INSTALL_TIMEOUT = ">>>>> Init Timed Out"
RESET_FAILED = ">>>>> Reset Failed"
TESTS_ERROR = ">>>>> Tests Errored"
TESTS_FAILED = ">>>>> Some Tests Failed"
TESTS_PASSED = ">>>>> All Tests Passed"
TESTS_TIMEOUT = ">>>>> Tests Timed Out"


# Constants - Miscellaneous
NON_TEST_EXTS = [
    ".json",
    ".png",
    "csv",
    ".txt",
    ".md",
    ".jpg",
    ".jpeg",
    ".pkl",
    ".yml",
    ".yaml",
    ".toml",
]
