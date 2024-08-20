import sys
import pytest


class Plugin:
    def __init__(self):
        self.collected_tests = []

    def pytest_sessionfinish(self, session, exitstatus):
        # Collect test node IDs into the list
        for item in session.items:
            self.collected_tests.append(item.nodeid)


def list_pytest_functions(path):
    plugin = Plugin()
    # Run pytest in "collect-only" mode and use our custom plugin
    pytest.main(["--collect-only", path], plugins=[plugin])
    for one in plugin.collected_tests:
        print(one)

if __name__ == '__main__':
    list_pytest_functions(sys.argv[1])
