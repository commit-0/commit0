from __future__ import annotations

import docker
import logging
import os
import signal
import tarfile
import threading
import time
import traceback
from pathlib import Path
from io import BytesIO

from docker.models.containers import Container

HEREDOC_DELIMITER = "EOF_1399519320"  # different from dataset HEREDOC_DELIMITERs!


def copy_to_container(container: Container, src: Path, dst: Path) -> None:
    """Copy a file from local to a docker container

    Args:
    ----
        container (Container): Docker container to copy to
        src (Path): Source file path
        dst (Path): Destination file path in the container

    """
    # Check if destination path is valid
    if os.path.dirname(dst) == "":
        raise ValueError(
            f"Destination path parent directory cannot be empty!, dst: {dst}"
        )

    # temporary tar file
    tar_path = src.with_suffix(".tar")
    with tarfile.open(tar_path, "w") as tar:
        tar.add(src, arcname=src.name)

    # get bytes for put_archive cmd
    with open(tar_path, "rb") as tar_file:
        data = tar_file.read()

    # Make directory if necessary
    container.exec_run(f"mkdir -p {dst.parent}")

    # Send tar file to container and extract
    container.put_archive(os.path.dirname(dst), data)
    container.exec_run(f"tar -xf {dst}.tar -C {dst.parent}")

    # clean up in locally and in container
    tar_path.unlink()
    container.exec_run(f"rm {dst}.tar")


def copy_from_container(container: Container, src: Path, dst: Path) -> None:
    """Copy a file from a docker container to local

    Args:
    ----
        container (Container): Docker container to copy from
        src (Path): Source file path in the container
        dst (Path): Destination file path locally

    """
    if not isinstance(src, Path):
        src = Path(src)

    if not isinstance(dst, Path):
        dst = Path(dst)

    # Ensure destination directory exists
    if not dst.parent.exists():
        os.makedirs(dst.parent)

    # Copy the file out of the container
    stream, stat = container.get_archive(str(src))

    # Create a temporary tar file
    tar_stream = BytesIO()
    for chunk in stream:
        tar_stream.write(chunk)
    tar_stream.seek(0)

    with tarfile.open(fileobj=tar_stream, mode="r") as tar:
        # Extract file from tar stream
        def is_within_directory(directory, target):
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)

            prefix = os.path.commonprefix([abs_directory, abs_target])

            return prefix == abs_directory

        def safe_extract(tar, path=".", members=None, *, numeric_owner=False) -> None:
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")

            tar.extractall(path, members, numeric_owner=numeric_owner)

        safe_extract(tar, path=dst.parent)

    # Move the extracted file to desired dst path if tar extraction gives src.name
    extracted_file_path = dst.parent / src.name
    if extracted_file_path != dst:
        extracted_file_path.rename(dst)


def delete_file_from_container(container: Container, file_path: str) -> None:
    """Delete a file from a docker container.

    Args:
    ----
        container (Container): Docker container to delete the file from
        file_path (str): Path to the file in the container to be deleted

    Raises:
    ------
        docker.errors.APIError: If there is an error calling the Docker API.
        Exception: If the file deletion command fails with a non-zero exit code.

    """
    try:
        exit_code, output = container.exec_run(f"rm -f {file_path}")
        if exit_code != 0:
            raise Exception(f"Error deleting file: {output.decode('utf-8').strip()}")
    except docker.errors.APIError as e:
        raise docker.errors.APIError(f"Docker API Error: {str(e)}")
    except Exception as e:
        raise Exception(f"General Error: {str(e)}")


def copy_ssh_pubkey_from_container(container: Container) -> None:
    """Copy the SSH public key from a Docker container to the local authorized_keys file.

    Args:
    ----
    container (Container): Docker container to copy the key from.

    Raises:
    ------
    docker.errors.APIError: If there is an error calling the Docker API.
    Exception: If the file reading or writing process fails.

    """
    try:
        exit_code, output = container.exec_run("cat /root/.ssh/id_rsa.pub")
        if exit_code != 0:
            raise Exception(f"Error reading file: {output.decode('utf-8').strip()}")
        public_key = output.decode("utf-8").strip()

        local_authorized_keys_path = os.path.expanduser("~/.ssh/authorized_keys")
        os.makedirs(os.path.dirname(local_authorized_keys_path), exist_ok=True)

        with open(local_authorized_keys_path, "r") as authorized_keys_file:
            content = authorized_keys_file.read()
            if public_key not in content:
                write = True
            else:
                write = False

        if write:
            with open(local_authorized_keys_path, "a") as authorized_keys_file:
                authorized_keys_file.write(public_key + "\n")

    except docker.errors.APIError as e:
        raise docker.errors.APIError(f"Docker API Error: {str(e)}")
    except Exception as e:
        raise Exception(f"General Error: {str(e)}")


def write_to_container(container: Container, data: str, dst: Path) -> None:
    """Write a string to a file in a docker container"""
    # echo with heredoc to file
    command = f"cat <<'{HEREDOC_DELIMITER}' > {dst}\n{data}\n{HEREDOC_DELIMITER}"
    container.exec_run(command)


def remove_image(client, image_id, logger=None) -> None:
    """Remove a Docker image by ID.

    Args:
    ----
        client (docker.DockerClient): Docker client.
        image_id (str): Image ID.
        rm_image (bool): Whether to remove the image.
        logger (logging.Logger): Logger to use for output. If None, print to stdout.

    """
    if not logger:
        # if logger is None, print to stdout
        log_info = print
        log_error = print
        raise_error = True
    elif logger == "quiet":
        # if logger is "quiet", don't print anything
        def log_info(x) -> None:
            return None

        def log_error(x) -> None:
            return None

        raise_error = True
    else:
        # if logger is a logger object, use it
        log_error = logger.info
        log_info = logger.info
        raise_error = False
    try:
        log_info(f"Attempting to remove image {image_id}...")
        client.images.remove(image_id, force=True)
        log_info(f"Image {image_id} removed.")
    except docker.errors.ImageNotFound:
        log_info(f"Image {image_id} not found, removing has no effect.")
    except Exception as e:
        if raise_error:
            raise e
        log_error(
            f"Failed to remove image {image_id}: {e}\n" f"{traceback.format_exc()}"
        )


def cleanup_container(client, container, logger) -> None:
    """Stop and remove a Docker container.
    Performs this forcefully if the container cannot be stopped with the python API.

    Args:
    ----
        client (docker.DockerClient): Docker client.
        container (docker.models.containers.Container): Container to remove.
        logger (logging.Logger): Logger to use for output. If None, print to stdout

    """
    if not container:
        return

    container_id = container.id

    if not logger:
        # if logger is None, print to stdout
        log_error = print
        log_info = print
        raise_error = True
    elif logger == "quiet":
        # if logger is "quiet", don't print anything
        def log_info(x) -> None:
            return None

        def log_error(x) -> None:
            return None

        raise_error = True
    else:
        # if logger is a logger object, use it
        log_error = logger.info
        log_info = logger.info
        raise_error = False

    # Attempt to stop the container
    try:
        if container:
            log_info(f"Attempting to stop container {container.name}...")
            container.stop(timeout=15)
    except Exception as e:
        log_error(
            f"Failed to stop container {container.name}: {e}. Trying to forcefully kill..."
        )
        try:
            # Get the PID of the container
            container_info = client.api.inspect_container(container_id)
            pid = container_info["State"].get("Pid", 0)

            # If container PID found, forcefully kill the container
            if pid > 0:
                log_info(
                    f"Forcefully killing container {container.name} with PID {pid}..."
                )
                os.kill(pid, signal.SIGKILL)
            else:
                log_error(f"PID for container {container.name}: {pid} - not killing.")
        except Exception as e2:
            if raise_error:
                raise e2
            log_error(
                f"Failed to forcefully kill container {container.name}: {e2}\n"
                f"{traceback.format_exc()}"
            )

    # Attempt to remove the container
    try:
        log_info(f"Attempting to remove container {container.name}...")
        container.remove(force=True)
        log_info(f"Container {container.name} removed.")
    except Exception as e:
        if raise_error:
            raise e
        log_error(
            f"Failed to remove container {container.name}: {e}\n"
            f"{traceback.format_exc()}"
        )


def create_container(
    client: docker.DockerClient,
    image_name: str,
    container_name: str = None,
    user: str = None,
    command: str = None,
    nano_cpus: int = None,
    logger: logging.Logger = None,
) -> Container:
    """Start a Docker container using the specified image.

    Args:
    ----
            client (docker.DockerClient): Docker client.
    image_name (str): The name of the Docker image.
    container_name (str, optional): Name for the Docker container. Defaults to None.
            user (str, option): Log in as which user. Defaults to None.
    command (str, optional): Command to run in the container. Defaults to None.
            nano_cpus (int, optional): The number of CPUs for the container. Defaults to None.
    logger (logging.Logger, optional): Port mappings. Defaults to None.

    Returns:
    -------
    docker.models.containers.Container: The started Docker container.

    Raises:
    ------
    docker.errors.APIError: If there's an error interacting with the Docker API.
    Exception: For other general errors.

    """
    # try:
    #    # Pull the image if it doesn't already exist
    #    client.images.pull(image_name)
    # except docker.errors.APIError as e:
    #    raise docker.errors.APIError(f"Error pulling image: {str(e)}")

    if not logger:
        # if logger is None, print to stdout
        log_error = print
        log_info = print
    elif logger == "quiet":
        # if logger is "quiet", don't print anything
        def log_info(x) -> None:
            return None

        def log_error(x) -> None:
            return None
    else:
        # if logger is a logger object, use it
        log_error = logger.info
        log_info = logger.info

    container = None
    try:
        logger.info(f"Creating container for {image_name}...")
        container = client.containers.run(
            image=image_name,
            name=container_name,
            user=user,
            command="tail -f /dev/null",
            nano_cpus=nano_cpus,
            detach=True,
        )
        logger.info(f"Container for {image_name} created: {container.id}")
        return container
    except Exception as e:
        # If an error occurs, clean up the container and raise an exception
        logger.error(f"Error creating container for {image_name}: {e}")
        logger.info(traceback.format_exc())
        cleanup_container(client, container, logger)
        raise


def exec_run_with_timeout(container, cmd, timeout: int | None = 60):
    """Run a command in a container with a timeout.

    Args:
    ----
        container (docker.Container): Container to run the command in.
        cmd (str): Command to run.
        timeout (int): Timeout in seconds.

    """
    # Local variables to store the result of executing the command
    exec_result = ""
    exec_id = None
    exception = None
    timed_out = False

    # Wrapper function to run the command
    def run_command() -> None:
        nonlocal exec_result, exec_id, exception
        try:
            exec_id = container.client.api.exec_create(container.id, cmd)["Id"]
            exec_stream = container.client.api.exec_start(exec_id, stream=True)
            for chunk in exec_stream:
                exec_result += chunk.decode("utf-8", errors="replace")
        except Exception as e:
            exception = e

    # Start the command in a separate thread
    thread = threading.Thread(target=run_command)
    start_time = time.time()
    thread.start()
    thread.join(timeout)

    if exception:
        raise exception

    # If the thread is still alive, the command timed out
    if thread.is_alive():
        if exec_id is not None:
            exec_pid = container.client.api.exec_inspect(exec_id)["Pid"]
            container.exec_run(f"kill -TERM {exec_pid}", detach=True)
        timed_out = True
    end_time = time.time()
    return exec_result, timed_out, end_time - start_time


def find_dependent_images(client: docker.DockerClient, image_name: str):
    """Find all images that are built upon `image_name` image

    Args:
    ----
        client (docker.DockerClient): Docker client.
        image_name (str): Name of the base image.

    """
    dependent_images = []

    # Get all local images
    all_images = client.images.list()

    # Get the ID of the base image
    try:
        base_image = client.images.get(image_name)
        base_image_id = base_image.id
    except docker.errors.ImageNotFound:
        print(f"Base image {image_name} not found.")
        return []

    for image in all_images:
        # Skip the base image itself
        if image.id == base_image_id:
            continue

        # Check if the base image is in this image's history
        history = image.history()
        for layer in history:
            if layer["Id"] == base_image_id:
                # If found, add this image to the dependent images list
                tags = image.tags
                dependent_images.append(tags[0] if tags else image.id)
                break

    return dependent_images


def list_images(client: docker.DockerClient):
    """List all images from the Docker client."""
    # don't use this in multi-threaded context
    return {tag for i in client.images.list(all=True) for tag in i.tags}


def clean_images(
    client: docker.DockerClient, prior_images: set, cache_level: str, clean: bool
) -> None:
    """Clean Docker images based on cache level and clean flag.

    Args:
    ----
        client (docker.DockerClient): Docker client.
        prior_images (set): Set of images that existed before the current run.
        cache (str): Cache level to use.
        clean (bool): Whether to clean; remove images that are higher in the cache hierarchy than the current
            cache level. E.g. if cache_level is set to env, remove all previously built instances images. if
            clean is false, previously built instances images will not be removed, but instance images built
            in the current run will be removed.

    """
    images = list_images(client)
    removed = 0
    print("Cleaning cached images...")
    for image_name in images:
        if should_remove(image_name, cache_level, clean, prior_images):
            try:
                remove_image(client, image_name, "quiet")
                removed += 1
            except Exception as e:
                print(f"Error removing image {image_name}: {e}")
                continue
    print(f"Removed {removed} images.")


def should_remove(
    image_name: str, cache_level: str, clean: bool, prior_images: set
) -> bool:
    """Determine if an image should be removed based on cache level and clean flag."""
    existed_before = image_name in prior_images
    if image_name.startswith("commit0.base"):
        if cache_level in {"none"} and (clean or not existed_before):
            return True
    elif image_name.startswith("commit0.repo"):
        if cache_level in {"none", "base"} and (clean or not existed_before):
            return True
    return False
