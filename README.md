# spec2repo

We strictly follow how SWE-bench does evaluation, where it uses Docker for reproducible evaluations.
Follow the instructions in the [Docker setup guide](https://docs.docker.com/engine/install/) to install Docker on your machine.
If you're setting up on Linux, we recommend seeing the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) as well.

Finally, to build SWE-bench from source, follow these steps:
```bash
cd evaluation/SWE-bench
pip install -e .
```

Then, to run evaluation for minitorch using the gold patch:
```
bash scripts/test_evaluate.sh
```
