import sys
import pytest
import multiprocessing


class Plugin:
    def __init__(self):
        self.collected_tests = []

    def pytest_sessionfinish(self, session, exitstatus):
        # Collect test node IDs into the list
        for item in session.items:
            self.collected_tests.append(item.nodeid)

class TestResults:
    def __init__(self):
        self.results = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":  # We consider only the 'call' phase
            result = {
                "nodeid": report.nodeid,
                "outcome": report.outcome,
                "duration": report.duration
            }
            self.results.append(result)

def list_pytest_functions(path):
    plugin = Plugin()
    pytest.main(["--collect-only", '-n', '4', path], plugins=[plugin])
    for one in plugin.collected_tests:
        print(f"[HERE]{one}")


def run_unit_tests(path):
    test_results = TestResults()

    # Run the tests and pass the TestResults instance as a plugin
    pytest.main(['-q', '--tb=short', '-n', '4', path], plugins=[test_results])

    # Print the collected results
    for result in test_results.results:
        nodeid = result['nodeid']
        outcome = result['outcome']
        duration = result['duration']
        print(f"[HERE]{nodeid}[SEPSEPSEP]{outcome}[SEPSEPSEP]{duration}")
    return test_results.results

if __name__ == '__main__':
    option = sys.argv[1]
    path = sys.argv[2]
    if option == "list":
        list_pytest_functions(path)
    elif option == "run":
        run_unit_tests(path)
