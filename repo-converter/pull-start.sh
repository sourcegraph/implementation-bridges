#!/bin/bash

# To be used in a cronjob to always pull and use the latest image
# so that the running container is only x minutes/hours behind the latest version of the docker-compose.yaml file, and the Docker image tagged latest in GitHub packages

# crontab -e
# */10 * * * * sudo bash /sourcegraph/implementation-bridges/repo-converter/pull-start.sh >> /sourcegraph/implementation-bridges/repo-converter/pull-start.log 2>&1

repo_converter_path="/sourcegraph/implementation-bridges/repo-converter"

git -C $repo_converter_path pull

docker compose -f $repo_converter_path/docker-compose.yaml up -d
