#!/bin/bash

# To be used in a cronjob to always pull and build the latest commit to the current branch
# every 10 minutes
# so that the running container is only 10 minutes behind the latest commit in the branch

# crontab -e
# */10 * * * * sudo bash /sourcegraph/implementation-bridges/repo-converter/build/pull-build-start.sh >> /sourcegraph/implementation-bridges/repo-converter/build/pull-build-start.log 2>&1

repo_converter_build_path="/sourcegraph/implementation-bridges/repo-converter/build"

git -C $repo_converter_build_path pull

docker compose -f $repo_converter_build_path/docker-compose.yaml up -d --build --remove-orphans
