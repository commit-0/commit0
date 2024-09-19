# Distributed

One of the main advantages of `commit0` is that it can run
a range of unit tests in distributed environments.

By default, the library is configured to work with [modal](https://modal.com/).

```bash
pip install modal
modal token new
```

## Modal Setup

To enable distributed run, first
create a file called `distributed.yaml`

```yaml
backend: modal
base_dir: repos.dist/
```

You can pass this configuration file as an argumnet to clone.

```bash
commit0 clone lite --cfg=distributed
```

Next to run tests you can run the standard test command.

```bash
commit0 test simpy master tests/test_event.py::test_succeed --cfg=distributed
```
