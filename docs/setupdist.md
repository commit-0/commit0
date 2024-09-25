## Distributed Mode

Commit0 is a command-line tool that allows you to run unit-tests on a
variety of libraries in isolated environments.

The defaul tool uses [modal](https://modal.com/) as a distributed
test runner.

```bash
pip install modal
modal token new
```

To get started, run the `setup` command with the dataset
split that youare interested in working with.
We'll start with the `lite` split.

```bash
commit0 setup lite
```

This will clone a set of skeleton libraries in your `repos/` directory.
Commiting changes to branches in this directory is how you send changes
to the test runner.

Next to run tests you can run the standard test command.
This command will run a reference unit test for the `simpy` repo.

```bash
commit0 test simpy tests/test_event.py::test_succeed --reference
```

To run a test in your codebase you can run with no args.
This one will fail.

```bash
commit0 test simpy tests/test_event.py::test_succeed
```

To run a test in your codebase with a specific branch
you can commit to the branch and call with the --branch command.


```bash
commit0 test simpy tests/test_event.py::test_succeed --branch my_branch
```
