import logging
import re
import traceback
import docker
import docker.errors
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from commit0.harness.constants import (
    BASE_IMAGE_BUILD_DIR,
    REPO_IMAGE_BUILD_DIR,
)
from commit0.harness.spec import get_specs_from_dataset
from commit0.harness.utils import setup_logger, close_logger

ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class BuildImageError(Exception):
    def __init__(self, image_name: str, message: str, logger: logging.Logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.image_name = image_name
        self.log_path = ""  # logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Error building image {self.image_name}: {self.super_str}\n"
            f"Check ({self.log_path}) for more information."
        )


def build_image(
    image_name: str,
    setup_scripts: dict,
    dockerfile: str,
    platform: str,
    client: docker.DockerClient,
    build_dir: Path,
    nocache: bool = False,
) -> None:
    """Builds a docker image with the given name, setup scripts, dockerfile, and platform.

    Args:
    ----
        image_name (str): Name of the image to build
        setup_scripts (dict): Dictionary of setup script names to setup script contents
        dockerfile (str): Contents of the Dockerfile
        platform (str): Platform to build the image for
        client (docker.DockerClient): Docker client to use for building the image
        build_dir (Path): Directory for the build context (will also contain logs, scripts, and artifacts)
        nocache (bool): Whether to use the cache when building

    """
    # Create a logger for the build process
    logger = setup_logger(image_name, build_dir / "build_image.log")
    logger.info(
        f"Building image {image_name}\n"
        f"Using dockerfile:\n{dockerfile}\n"
        f"Adding ({len(setup_scripts)}) setup scripts to image build repo"
    )

    for setup_script_name, setup_script in setup_scripts.items():
        logger.info(f"[SETUP SCRIPT] {setup_script_name}:\n{setup_script}")
    try:
        # Write the setup scripts to the build directory
        for setup_script_name, setup_script in setup_scripts.items():
            setup_script_path = build_dir / setup_script_name
            with open(setup_script_path, "w") as f:
                f.write(setup_script)
            if setup_script_name not in dockerfile:
                logger.warning(
                    f"Setup script {setup_script_name} may not be used in Dockerfile"
                )

        # Write the dockerfile to the build directory
        dockerfile_path = build_dir / "Dockerfile"
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile)

        # Build the image
        logger.info(
            f"Building docker image {image_name} in {build_dir} with platform {platform}"
        )
        response = client.api.build(
            path=str(build_dir),
            tag=image_name,
            rm=True,
            forcerm=True,
            decode=True,
            platform=platform,
            nocache=nocache,
        )

        # Log the build process continuously
        for chunk in response:
            if "stream" in chunk:
                # Remove ANSI escape sequences from the log
                chunk_stream = ansi_escape.sub("", chunk["stream"])
                logger.info(chunk_stream.strip())
        logger.info("Image built successfully!")
    except docker.errors.APIError as e:
        logger.error(f"docker.errors.APIError during {image_name}: {e}")
        raise BuildImageError(image_name, str(e), logger) from e
    except Exception as e:
        logger.error(f"Error building image {image_name}: {e}")
        raise BuildImageError(image_name, str(e), logger) from e
    finally:
        close_logger(logger)  # functions that create loggers should close them


def build_base_images(client: docker.DockerClient, dataset: list) -> None:
    """Builds the base images required for the dataset if they do not already exist.

    Args:
    ----
        client (docker.DockerClient): Docker client to use for building the images
        dataset (list): List of test specs or dataset to build images for

    """
    # Get the base images to build from the dataset
    test_specs = get_specs_from_dataset(dataset)
    base_images = {
        x.base_image_key: (x.base_dockerfile, x.platform) for x in test_specs
    }

    # Build the base images
    for image_name, (dockerfile, platform) in base_images.items():
        try:
            # Check if the base image already exists
            client.images.get(image_name)
            print(f"Base image {image_name} already exists, skipping build.")
            continue
        except docker.errors.ImageNotFound:
            pass
        # Build the base image (if it does not exist or force rebuild is enabled)
        print(f"Building base image ({image_name})")
        build_image(
            image_name=image_name,
            setup_scripts={},
            dockerfile=dockerfile,
            platform=platform,
            client=client,
            build_dir=BASE_IMAGE_BUILD_DIR / image_name.replace(":", "__"),
        )
    print("Base images built successfully.")


def get_repo_configs_to_build(
    client: docker.DockerClient,
    dataset: list,
) -> dict[str, Any]:
    """Returns a dictionary of image names to build scripts and dockerfiles for repo images.
    Returns only the repo images that need to be built.

    Args:
    ----
        client (docker.DockerClient): Docker client to use for building the images
        dataset (list): List of test specs or dataset to build images for

    """
    image_scripts = dict()
    test_specs = get_specs_from_dataset(dataset)

    for test_spec in test_specs:
        # Check if the base image exists
        try:
            client.images.get(test_spec.base_image_key)
        except docker.errors.ImageNotFound:
            raise Exception(
                f"Base image {test_spec.base_image_key} not found for {test_spec.repo_image_key}\n."
                "Please build the base images first."
            )

        # Check if the repo image exists
        image_exists = False
        try:
            client.images.get(test_spec.repo_image_key)
            image_exists = True
        except docker.errors.ImageNotFound:
            pass
        if not image_exists:
            # Add the repo image to the list of images to build
            image_scripts[test_spec.repo_image_key] = {
                "setup_script": test_spec.setup_script,
                "dockerfile": test_spec.repo_dockerfile,
                "platform": test_spec.platform,
            }
    return image_scripts


def build_repo_images(
    client: docker.DockerClient,
    dataset: list,
    max_workers: int = 4,
    verbose: int = 1,
) -> tuple[list[str], list[str]]:
    """Builds the repo images required for the dataset if they do not already exist.

    Args:
    ----
        client (docker.DockerClient): Docker client to use for building the images
        dataset (list): List of test specs or dataset to build images for
        max_workers (int): Maximum number of workers to use for building images
        verbose (int): Level of verbosity

    Return:
    ------
        successful: a list of docker image keys for which build were successful
        failed: a list of docker image keys for which build failed

    """
    build_base_images(client, dataset)
    configs_to_build = get_repo_configs_to_build(client, dataset)
    if len(configs_to_build) == 0:
        print("No repo images need to be built.")
        return [], []
    print(f"Total repo images to build: {len(configs_to_build)}")

    # Build the repo images
    successful, failed = list(), list()
    with tqdm(
        total=len(configs_to_build), smoothing=0, desc="Building repo images"
    ) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for each image to build
            futures = {
                executor.submit(
                    build_image,
                    image_name,
                    {"setup.sh": config["setup_script"]},
                    config["dockerfile"],
                    config["platform"],
                    client,
                    REPO_IMAGE_BUILD_DIR / image_name.replace(":", "__"),
                ): image_name
                for image_name, config in configs_to_build.items()
            }

            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    # Update progress bar, check if image built successfully
                    future.result()
                    successful.append(futures[future])
                except BuildImageError as e:
                    print(f"BuildImageError {e.image_name}")
                    traceback.print_exc()
                    failed.append(futures[future])
                    continue
                except Exception:
                    print("Error building image")
                    traceback.print_exc()
                    failed.append(futures[future])
                    continue

    # Show how many images failed to build
    if len(failed) == 0:
        print("All repo images built successfully.")
    else:
        print(f"{len(failed)} repo images failed to build.")

    # Return the list of (un)successfuly built images
    return successful, failed


__all__ = []
