""" Modal utility functions

A mirror of the docker utility functions.
"""

import modal
import os

from commit0.harness.docker_utils import HEREDOC_DELIMITER


def create_sandbox(image: modal.Image, nfs: model.NetworkFileSystem) -> modal.Sandbox:
    return modal.Sandbox.create(
        "sleep",
        "infinity",
        image=image,
        network_file_systems={
            "/vol": nfs,
        },
    )


def execute_command(sandbox: modal.Sandbox, command: str, timeout=) -> tuple[str,str]:
    process = sandbox.exec("bash", "-c", command)
    stdout = []
    for line in process.stdout:
        stdout.append(line)
    stderr = []
    for line in process.stderr:
        stderr.append(line)
    return "\n".join(stdout), "\n".join(stderr)


def copy_file_to_sandbox(sandbox: modal.Sandbox, nfs: modal.NetworkFileSystem, src: Path, dst: Path) -> None:
    with src.open("rb") as f:
        nfs.write_file(str(src), f)
    sandbox.exec("bash", "-c", f"cp /vol/{str(src)} {str(dst)}")


def copy_from_sandbox(sandbox: modal.Sandbox, src: Path, dst: Path) -> None:
    pass


def delete_file_from_sandbox(sandbox: modal.Sandbox, file_path: str) -> None:
    pass


def copy_ssh_pubkey_from_sandbox(sandbox: modal.Sandbox) -> None:
    process = sandbox.exec("bash", "-c", "cat /root/.ssh/id_rsa.pub")
    public_key = "".join([line for line in process.stdout]).strip()

    # add to authorized keys locally. copy-pasted from utils
    local_authorized_keys_path = os.path.expanduser("~/.ssh/authorized_keys")
    os.makedirs(os.path.dirname(local_authorized_keys_path), exist_ok=True)
    if not os.path.exists(local_authorized_keys_path):
        # Since the file does not exist, create it
        open(local_authorized_keys_path, "a").close()
        write = True
    else:
        with open(local_authorized_keys_path, "r") as authorized_keys_file:
            content = authorized_keys_file.read()
            if public_key not in content:
                write = True
            else:
                write = False
    if write:
        with open(local_authorized_keys_path, "a") as authorized_keys_file:
            authorized_keys_file.write(public_key + "\n")


def write_to_sandbox(sandbox: modal.Sandbox, data: str, dst: Path) -> None:
    pass
