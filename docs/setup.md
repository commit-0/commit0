# Setup

## Install

First be sure that you have docker tools installed.

```bash
apt install docker
```

To install the benchmark run,

```bash
pip install commit0
```

## Commands

The system is a command-line tool that allows you to run unit-tests on a
variety of libraries in isolated environments. To get started with the full
setup run the `clone` command which will install a clone the code of a subset
of libraries to your `repos/` directory.

```bash
commit0 clone lit
```

Next run the `build` command which will configure Docker containers for
each of the libraries with isolated virtual environments. The command uses the
[uv](https://github.com/astral-sh/uv) library for efficient builds.

```bash
commit0 build lit
```

The main operation you can do with these enviroments is to run tests.
Here we run [a test](https://github.com/commit-0/simpy/blob/master/tests/test_event.py#L11) in the `simpy` library.

```bash
commit0 test simpy tests/test_event.py::test_succeed
```

This test should run and pass, but others will fail.

```bash
commit0 test minitorch tests/test_operators.py::test_relu
```

Let's now manually go in and change that repo.
This is all just standard shell commands.

```bash
cd repos/minitorch/
git checkout -b mychange
patch ../../minitorch.example.patch .
cd ../..
```

Once this is done we can run `test` with
a branch and the environment will sync and run.

```bash
commit0 test minitorch branch=mychange tests/test_operators.py::test_relu
```

## Running an Agent

Next we will see how this can be run with an agent system.

...

## Distributed Environments
