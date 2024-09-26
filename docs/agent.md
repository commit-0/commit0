## Running

Commit0 provides a command-line `agent` for configuring and
running AI agents to assist with code development and testing.
In this example we use [Aider](https://aider.chat/) as the
baseline code completion agent

```bash
pip install aider-chat
```

First we assume there is an underlying `commit0`
project that is configured. To create a new project,
run the commit0 `setup` command.

```bash
commit0 setup lite
```

Next we need to configure the backend for the agent.
Currently we only support the aider backend. Config
can also be used to pass in arguments.

```bash
export ANTHROPIC_API_KEY="..."
agent config aider
```

Finally we run the underlying agent. This will create a display
that shows the current progress of the agent. Specify the branch
you want to commit changes on.

```bash
agent run BRANCH
```


### Extending
Refer to `class Agents` in `agent/agents.py`. You can design your own agent by inheriting `Agents` class and implement the `run` method.

## Notes


* Aider automatically retries certain API errors. For details, see [here](https://github.com/paul-gauthier/aider/blob/75e1d519da9b328b0eca8a73ee27278f1289eadb/aider/sendchat.py#L17).
* When increasing `--max-parallel-repos`, be mindful of aider's [60-second retry timeout](https://github.com/paul-gauthier/aider/blob/75e1d519da9b328b0eca8a73ee27278f1289eadb/aider/sendchat.py#L39). Set this value according to your API tier to avoid RateLimitErrors stopping processes.
* Currently, agent will skip file with more than 1500 lines. See `agent/agent_utils.py#L199` for details.
* Running a full `all` commit0 split costs approximately $100 with Claude Sonnet 3.5.
