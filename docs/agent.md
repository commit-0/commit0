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
