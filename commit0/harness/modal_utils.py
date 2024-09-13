"""Modal utility functions

A mirror of the docker utility functions.
"""

import modal
import os
from pathlib import Path


def create_sandbox(image: modal.Image, nfs: modal.NetworkFileSystem) -> modal.Sandbox:
    """Create modal sandbox"""
    return modal.Sandbox.create(
        "sleep",
        "infinity",
        image=image,
        network_file_systems={
            "/vol": nfs,
        },
        timeout=60,
    )


def execute_command(
    sandbox: modal.Sandbox, command: str, timeout: int = 90
) -> tuple[str, str]:
    """Execute command on modal sandbox"""
    process = sandbox.exec("bash", "-c", command)
    stdout = []
    for line in process.stdout:
        stdout.append(line)
    stderr = []
    for line in process.stderr:
        stderr.append(line)
    return "\n".join(stdout), "\n".join(stderr)


def copy_file_to_sandbox(
    sandbox: modal.Sandbox, nfs: modal.NetworkFileSystem, src: Path, dst: Path
) -> None:
    """Copy file to modal sandbox"""
    path = "tmpfile"
    with src.open("rb") as f:
        nfs.write_file(path, f)
    sandbox.exec("bash", "-c", f"cp /vol/{path} {str(dst)}")


def copy_from_sandbox(sandbox: modal.Sandbox, src: Path, dst: Path) -> None:
    """Copy file from sandbox"""
    pass


def delete_file_from_sandbox(sandbox: modal.Sandbox, file_path: str) -> None:
    """Delete file on sandbox"""
    pass


def copy_ssh_pubkey_from_sandbox(sandbox: modal.Sandbox) -> None:
    """Copy SSH public key from sandbox"""
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
    """Write file to sandbox"""
    pass
