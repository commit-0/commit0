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
```

And apply and commit this patch.

```
--- a/minitorch/operators.py
+++ b/minitorch/operators.py
@@ -81,7 +81,7 @@ def relu(x: float) -> float:
     (See https://en.wikipedia.org/wiki/Rectifier_(neural_networks) .)
     """
     # TODO: Implement for Task 0.1.
-    raise NotImplementedError('Need to implement for Task 0.1')
+    return 1. if x > 0. else 0.
```

Once this is done we can run `test` with
a branch and the environment will sync and run.

```bash
commit0 test minitorch branch=mychange tests/test_operators.py::test_relu
```

## Running an Agent

Next we will see how this can be run with an AI agent system.
We will use [Aider](https://aider.chat/) which is a nice
command-line oriented agent system.

To setup Aider first set your api key.
We recommend using Claude Sonnet.

```bash
# Work with Claude 3.5 Sonnet on your repo
export ANTHROPIC_API_KEY=your-key-goes-here
```

Once this is setup you can run Aider with the following command.
This will edit the files locally in your branch, but
run the tests inside the environment.

```bash
aider --model sonnet --file repos/minitorch/operators.py --message "fill in" \
     --auto-test --test \
     --test-cmd 'commit0 test minitorch branch=mychange tests/test_operators.py::test_relu' \
     --yes
```

This will run an LLM agent that will try to fill in the
functions in one file of the minitorch library.

For a full example baseline system that tries to solve
all the tests in the library see the [baseline](baseline) documentation.
