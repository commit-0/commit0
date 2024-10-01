from enum import Enum
from pathlib import Path
from typing import Dict, TypedDict


class RepoInstance(TypedDict):
    repo: str
    base_commit: str
    reference_commit: str
    setup: dict
    test: Dict[str, str]
    src_dir: str


class Files(TypedDict):
    eval_script: Dict[str, Path]
    patch: Dict[str, Path]


BASE_BRANCH = "commit0"

# Constants - Evaluation Log Directories
BASE_IMAGE_BUILD_DIR = Path("logs/build_images/base")
REPO_IMAGE_BUILD_DIR = Path("logs/build_images/repo")
RUN_PYTEST_LOG_DIR = Path("logs/pytest")
RUN_AGENT_LOG_DIR = Path("logs/agent")

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
    "portalocker",
    "parsel",
    "pyjwt",
    "chardet",
    "babel",
    "minitorch",
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
SPLIT_MINITORCH = ["minitorch"]
SPLIT_SIMPY = ["simpy"]
SPLIT_STATSMODELS = ["statsmodels"]
SPLIT_PYTHON_PROGRESSBAR = ["python-progressbar"]
SPLIT_XARRAY = ["xarray"]
SPLIT_IMBALANCED_LEARN = ["imbalanced-learn"]
SPLIT_WEB3_PY = ["web3.py"]
SPLIT_SCRAPY = ["scrapy"]
SPLIT_SEABORN = ["seaborn"]
SPLIT_PYPDF = ["pypdf"]
SPLIT_PEXPECT = ["pexpect"]
SPLIT_PYTEST = ["pytest"]
SPLIT_PYLINT = ["pylint"]
SPLIT_JOBLIB = ["joblib"]
SPLIT_DULWICH = ["dulwich"]
SPLIT_VIRTUALENV = ["virtualenv"]
SPLIT_NETWORKX = ["networkx"]
SPLIT_REQUESTS = ["requests"]
SPLIT_SPHINX = ["sphinx"]
SPLIT_JEDI = ["jedi"]
SPLIT_MOVIEPY = ["moviepy"]
SPLIT_LOGURU = ["loguru"]
SPLIT_PARAMIKO = ["paramiko"]
SPLIT_GEOPANDAS = ["geopandas"]
SPLIT_BITSTRING = ["bitstring"]
SPLIT_FASTAPI = ["fastapi"]
SPLIT_CHARDET = ["chardet"]
SPLIT_TORNADO = ["tornado"]
SPLIT_PYTHON_PROMPT_TOOLKIT = ["python-prompt-toolkit"]
SPLIT_ATTRS = ["attrs"]
SPLIT_PYBOY = ["PyBoy"]
SPLIT_PYDANTIC = ["pydantic"]
SPLIT_FILESYSTEM_SPEC = ["filesystem_spec"]
SPLIT_TLSLITE_NG = ["tlslite-ng"]
SPLIT_GRAPHENE = ["graphene"]
SPLIT_MIMESIS = ["mimesis"]
SPLIT_BABEL = ["babel"]
SPLIT_DNSPYTHON = ["dnspython"]
SPLIT_PORTALOCKER = ["portalocker"]
SPLIT_COOKIECUTTER = ["cookiecutter"]
SPLIT_PYJWT = ["pyjwt"]
SPLIT_PYTHON_RSA = ["python-rsa"]
SPLIT_MORE_ITERTOOLS = ["more-itertools"]
SPLIT_CLICK = ["click"]
SPLIT_FABRIC = ["fabric"]
SPLIT_JINJA = ["jinja"]
SPLIT_FLASK = ["flask"]
SPLIT_SQLPARSE = ["sqlparse"]
SPLIT_MARSHMALLOW = ["marshmallow"]
SPLIT_IMAPCLIENT = ["imapclient"]
SPLIT_TINYDB = ["tinydb"]
SPLIT_CACHETOOLS = ["cachetools"]
SPLIT_VOLUPTUOUS = ["voluptuous"]
SPLIT_PARSEL = ["parsel"]
SPLIT_WCWIDTH = ["wcwidth"]
SPLIT_DEPRECATED = ["deprecated"]

SPLIT = {
    "all": SPLIT_ALL,
    "lite": SPLIT_LITE,
    "statsmodels": SPLIT_STATSMODELS,
    "python-progressbar": SPLIT_PYTHON_PROGRESSBAR,
    "xarray": SPLIT_XARRAY,
    "imbalanced-learn": SPLIT_IMBALANCED_LEARN,
    "web3.py": SPLIT_WEB3_PY,
    "scrapy": SPLIT_SCRAPY,
    "seaborn": SPLIT_SEABORN,
    "pypdf": SPLIT_PYPDF,
    "pexpect": SPLIT_PEXPECT,
    "pytest": SPLIT_PYTEST,
    "pylint": SPLIT_PYLINT,
    "joblib": SPLIT_JOBLIB,
    "dulwich": SPLIT_DULWICH,
    "virtualenv": SPLIT_VIRTUALENV,
    "minitorch": SPLIT_MINITORCH,
    "networkx": SPLIT_NETWORKX,
    "requests": SPLIT_REQUESTS,
    "sphinx": SPLIT_SPHINX,
    "jedi": SPLIT_JEDI,
    "moviepy": SPLIT_MOVIEPY,
    "loguru": SPLIT_LOGURU,
    "paramiko": SPLIT_PARAMIKO,
    "geopandas": SPLIT_GEOPANDAS,
    "bitstring": SPLIT_BITSTRING,
    "fastapi": SPLIT_FASTAPI,
    "chardet": SPLIT_CHARDET,
    "tornado": SPLIT_TORNADO,
    "python-prompt-toolkit": SPLIT_PYTHON_PROMPT_TOOLKIT,
    "attrs": SPLIT_ATTRS,
    "PyBoy": SPLIT_PYBOY,
    "pydantic": SPLIT_PYDANTIC,
    "filesystem_spec": SPLIT_FILESYSTEM_SPEC,
    "tlslite-ng": SPLIT_TLSLITE_NG,
    "graphene": SPLIT_GRAPHENE,
    "mimesis": SPLIT_MIMESIS,
    "babel": SPLIT_BABEL,
    "dnspython": SPLIT_DNSPYTHON,
    "portalocker": SPLIT_PORTALOCKER,
    "cookiecutter": SPLIT_COOKIECUTTER,
    "pyjwt": SPLIT_PYJWT,
    "python-rsa": SPLIT_PYTHON_RSA,
    "more-itertools": SPLIT_MORE_ITERTOOLS,
    "simpy": SPLIT_SIMPY,
    "click": SPLIT_CLICK,
    "fabric": SPLIT_FABRIC,
    "jinja": SPLIT_JINJA,
    "flask": SPLIT_FLASK,
    "sqlparse": SPLIT_SQLPARSE,
    "marshmallow": SPLIT_MARSHMALLOW,
    "imapclient": SPLIT_IMAPCLIENT,
    "tinydb": SPLIT_TINYDB,
    "cachetools": SPLIT_CACHETOOLS,
    "voluptuous": SPLIT_VOLUPTUOUS,
    "parsel": SPLIT_PARSEL,
    "wcwidth": SPLIT_WCWIDTH,
    "deprecated": SPLIT_DEPRECATED,
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
