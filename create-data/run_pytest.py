import sys
import pytest

SOS = "[HERE]"
SEP = "[SEPSEPSEP]"

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

def decide_num_workers(path):
    if 'marshmallow' in path:
        return '4'
    elif 'web3.py' in path:
        return '2'
    else:
        return '8'

def list_pytest_functions(path):
    plugin = Plugin()
    num_workers = decide_num_workers(path)
    pytest.main(["--collect-only", '-n', num_workers, path], plugins=[plugin])
    for one in plugin.collected_tests:
        print(f"{SOS}{one}")


def run_unit_tests(path):
    test_results = TestResults()

    num_workers = decide_num_workers(path)
    # Run the tests and pass the TestResults instance as a plugin
    pytest.main(['-q', '--tb=short', '-n', num_workers, path], plugins=[test_results])

    # Print the collected results
    for result in test_results.results:
        nodeid = result['nodeid']
        outcome = result['outcome']
        duration = result['duration']
        print(f"{SOS}{nodeid}{SEP}{outcome}{SEP}{duration}")
    return test_results.results

if __name__ == '__main__':
    option = sys.argv[1]
    path = sys.argv[2]
    if option == "list":
        list_pytest_functions(path)
    elif option == "run":
        run_unit_tests(path)
