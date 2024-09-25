## Local Mode

To run in local mode you first be sure that you have [docker tools](https://docs.docker.com/desktop/install/mac-install/)
installed. On Debian systems:

```bash
apt install docker
```

To get started, run the `setup` command with the dataset
split that you are interested in working with.
We'll start with the `lite` split.


```bash
commit0 setup lite
```

This will install a clone the code for subset of libraries to your `repos/` directory.

Next run the `build` command which will configure Docker containers for
each of the libraries with isolated virtual environments. The command uses the
[uv](https://github.com/astral-sh/uv) library for efficient builds.

```bash
commit0 build
```

The main operation you can do with these enviroments is to run tests.
Here we run [a test](https://github.com/commit-0/simpy/blob/master/tests/test_event.py#L11) in the `simpy` library.

```bash
commit0 test simpy tests/test_event.py::test_succeed
```

See [distributed setup](/setupdist) for more commands.
