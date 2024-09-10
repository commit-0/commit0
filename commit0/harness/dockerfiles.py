# IF you change the base image, you need to rebuild all images (run with --force_rebuild)
_DOCKERFILE_BASE = r"""
FROM --platform={platform} ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt install -y \
wget \
git \
build-essential \
libffi-dev \
libtiff-dev \
python3 \
python3-pip \
python-is-python3 \
jq \
curl \
locales \
locales-all \
tzdata \
&& rm -rf /var/lib/apt/lists/*

# Define arguments for SSH key parameters
ARG SSH_KEY_PATH="/root/.ssh"
ARG SSH_KEY_NAME="id_rsa"
ARG SSH_KEY_PASSPHRASE=""

# Create the .ssh directory
RUN mkdir -p ${{SSH_KEY_PATH}}

# Generate SSH keys
RUN ssh-keygen -t rsa -b 4096 -f ${{SSH_KEY_PATH}}/${{SSH_KEY_NAME}} -N "${{SSH_KEY_PASSPHRASE}}"

# Set up uv
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.cargo/bin/:$PATH"
"""

_DOCKERFILE_REPO = r"""FROM --platform={platform} commit0.base:latest

COPY ./setup.sh /root/
RUN chmod +x /root/setup.sh
RUN /bin/bash /root/setup.sh

WORKDIR /testbed/

# Automatically activate the testbed environment
RUN echo "source /testbed/.venv/bin/activate" > /root/.bashrc
"""


def get_dockerfile_base(platform: str) -> str:
    return _DOCKERFILE_BASE.format(platform=platform)


def get_dockerfile_repo(platform: str) -> str:
    return _DOCKERFILE_REPO.format(platform=platform)


__all__ = []
