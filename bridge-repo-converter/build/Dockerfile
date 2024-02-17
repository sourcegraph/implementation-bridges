# syntax=docker/dockerfile:1

# Using Ubuntu LTS
FROM ubuntu:22.04 as base

# Avoid stuck build due to user prompt
ARG DEBIAN_FRONTEND=noninteractive

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering
ENV PYTHONUNBUFFERED=1

# Install python
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y \
        cron \
        default-jre \
        git \
        git-svn \
        python3 \
        python3-pip \
        python3-wheel \
        subversion \
        systemctl \
        vim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    systemctl enable cron && \
    systemctl start cron

# Download dependencies as a separate step to take advantage of Docker's caching
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer
# Install requirements
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python3 -m pip install -r requirements.txt

# # Create sourcegraph user
# RUN useradd sourcegraph
# USER sourcegraph

# Copy the source code into the container
WORKDIR /sourcegraph
COPY . .

# Start the container
CMD ["/bin/bash", "/sourcegraph/setup.sh"]
