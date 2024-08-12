import re

from swebench.harness.constants import TestStatus
from swebench.harness.log_parsers import (
    parse_log_pytest_options
)

def parse_log_tinydb(log: str) -> dict[str, str]:
    """
    Parser for test logs generated with TinyDB framework

    Args:
        log (str): log content
    Returns:
        dict: test case to test status mapping
    """
    test_status_map = {}
    pattern = r"^(.*\/.*)::(.*)\s+\w+\s+\[\s*(\d+%)\]$"
    for line in log.split("\n"):
        line = line.strip()
        m = re.match(pattern, line)
        if m:
            line = line.split()
            test, value = line[:2]
            if value == "PASSED":
                test_status_map[test] = TestStatus.PASSED.value
            else:
                test_status_map[test] = TestStatus.FAILED.value
    return test_status_map

ADD_MAP_REPO_TO_PARSER = {
    "spec2repo/tinydb": parse_log_tinydb,
    "spec2repo/minitorch": parse_log_pytest_options,
}
