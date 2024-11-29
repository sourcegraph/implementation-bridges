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
git_cmd="git -C $repo_converter_dir"
docker_compose_file_path="$repo_converter_dir/docker-compose.yaml"
docker_cmd="docker compose -f $docker_compose_file_path"

# Log to both stdout and log file
exec > >(tee -a "$log_file") 2>&1

function log() {
    # Define log function for consistent output format
    echo "$(date '+%Y-%m-%d - %H:%M:%S') - $0 - $1"
}

log "Script starting"

command="\
    $git_cmd reset --hard                && \
    $git_cmd pull --force                && \
    $docker_cmd pull                     && \
    $docker_cmd up -d --remove-orphans      \
    "

log "Running command in subshell: $command"
bash -c "$command" >> "$log_file" 2>&1

log "Script finishing"
