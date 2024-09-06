First be sure that you have docker tools installed.

```bash
apt install docker
```

To install the benchmark run,

```bash
pip install spec2repo
```

Then run

```bash
spec2repo new local
```

This will generate a file `spec2repo.yml` in your project.
To launch the benchmark suite run

```bash
spec2repo launch
```

This will launch a set of docker instances for each of the repos as well as a
local master.

Now let's apply a patch to one of our repos:

```bash
cd repos/minitorch/
git checkout -b first_change
patch ../../minitorch.example.patch .
spec2repo test minitorch first_change test_add
```

This will run the `test_add` in the MiniTorch Repository and show the results.

To get your current score on a repository you can run

```bash
spec2repo score minitorch
```

## Running Aider

...
