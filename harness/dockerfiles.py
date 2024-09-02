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

_DOCKERFILE_REPO = r"""FROM --platform={platform} spec2repo.base:latest

COPY ./setup.sh /root/
RUN chmod +x /root/setup.sh
RUN /bin/bash /root/setup.sh

WORKDIR /testbed/

# Automatically activate the testbed environment
RUN echo "source /testbed/.venv/bin/activate" > /root/.bashrc
"""


def get_dockerfile_base(platform):
    return _DOCKERFILE_BASE.format(platform=platform)


def get_dockerfile_repo(platform):
    return _DOCKERFILE_REPO.format(platform=platform)
