#!/bin/bash

# To be used in a cronjob to always pull and use the latest image
# so that the running container is only x minutes/hours behind the latest version of the docker-compose.yaml file, and the Docker image tagged latest in GitHub packages

# crontab -e
# */10 * * * * sudo bash /sourcegraph/implementation-bridges/repo-converter/pull-start.sh

sg_root_dir="/sourcegraph"
log_file="$repo_converter_dir/pull-start.log"

repo_converter_dir="$sg_root_dir/implementation-bridges/repo-converter"

date_time=$(date +"%F %T")
echo "$date_time - Starting $0" >> "$log_file"

command="git -C $repo_converter_dir pull && docker compose -f $repo_converter_dir/docker-compose.yaml up -d"

bash -c "$command" >> "$log_file" 2>&1
