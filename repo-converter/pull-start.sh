#!/bin/bash

# To be used in a cronjob to always pull and use the latest image
# so that the running container is only x minutes/hours behind the latest version of
# the docker-compose.yaml file
# and the Docker image tagged latest in GitHub packages

# crontab -e
# */30 * * * * bash /sg/implementation-bridges/repo-converter/pull-start.sh

# What do I want the input to be?
# Path to docker-compose.yaml, be it repo-converter, or host-wsl
# Default to repo-converter

repo_dir="/sg/implementation-bridges"
repo_converter_dir="$repo_dir/repo-converter"
docker_compose_file_name="docker-compose.yaml"


if [[ -n "$1" && -f "$repo_dir/$1/$docker_compose_file_name" ]]; then
    docker_compose_file_dir="$repo_dir/$1"
else
    docker_compose_file_dir="$repo_converter_dir"
fi

docker_compose_file_path="$docker_compose_file_dir/$docker_compose_file_name"

log_file="$docker_compose_file_dir/pull-start.log"
docker_cmd="docker compose -f $docker_compose_file_path"
docker_up_sleep_seconds=10

git_cmd="git -C $repo_dir"

function log() {
    # Define log function for consistent output format
    echo "$(date '+%Y-%m-%d - %H:%M:%S') - $0 - $1"
}

# Log to both stdout and log file
exec > >(tee -a "$log_file") 2>&1

log "Script starting"
log "Running as user: $USER"
log "On branch: $($git_cmd branch -v)"
log "Docker compose file: $docker_compose_file_path"

command="\
    $git_cmd reset --hard                && \
    $git_cmd pull --force                && \
    $docker_cmd pull                     && \
    $docker_cmd up -d --remove-orphans      \
    "

log "Running command in a sub shell:"
# awk command to print the command nicely with newlines
echo "$command" | awk 'BEGIN{FS="&&"; OFS="&& \n"} {$1=$1} 1'

# Run the command
bash -c "$command" >> "$log_file" 2>&1

log "Sleeping $docker_up_sleep_seconds seconds to give Docker containers time to start and stabilize"
sleep $docker_up_sleep_seconds

log "docker ps:"
$docker_cmd ps

log "Script finishing"
