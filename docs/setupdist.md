## Distributed Mode

Commit0 is a command-line tool that allows you to run unit-tests on a
variety of libraries in isolated environments.

Commit0 uses [modal](https://modal.com/) as a distributed
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
Commiting changes to branches in this directory





You can pass this configuration file as an argumnet to clone.

```bash
commit0 setup lite
```

Next to run tests you can run the standard test command.

```bash
commit0 test simpy tests/test_event.py::test_succeed
```
