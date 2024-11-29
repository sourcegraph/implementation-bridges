#!/bin/bash

# To be used in a cronjob to always pull and use the latest image
# so that the running container is only x minutes/hours behind the latest version of
# the docker-compose.yaml file
# and the Docker image tagged latest in GitHub packages

# crontab -e
# */30 * * * * bash /sourcegraph/implementation-bridges/repo-converter/pull-start.sh

sg_root_dir="/sourcegraph"
repo_converter_dir="$sg_root_dir/implementation-bridges/repo-converter"
log_file="$repo_converter_dir/pull-start.log"

# Log to both stdout and log file
exec > >(tee -a "$log_file") 2>&1

function log() {
    # Define log function for consistent output format
    echo "$(date '+%Y-%m-%d - %H:%M:%S') - $0 - $1"
}

log "Script starting"

command="\
    sudo git -C $repo_converter_dir reset --hard                                            && \
    sudo git -C $repo_converter_dir pull --force                                            && \
    sudo docker compose -f $repo_converter_dir/docker-compose.yaml pull                     && \
    sudo docker compose -f $repo_converter_dir/docker-compose.yaml up -d --remove-orphans      \
    "

log "Running command in subshell: $command"
bash -c "$command" >> "$log_file" 2>&1

log "Script finishing"
