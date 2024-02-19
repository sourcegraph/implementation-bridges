#!/bin/bash

# To be used in a cronjob to always pull and build the latest
# every 10 minutes
# so that the running container is only 10 minutes behind the latest commit in the branch

# crontab -e
# */10 * * * * bash /sourcegraph/implementation-bridges/host-wsl2-ubuntu/pull-build-start.sh >> /sourcegraph/implementation-bridges/host-wsl2-ubuntu/pull-build-start.log 2>&1

repo_build_path="/sourcegraph/implementation-bridges/repo-converter/build"

git -C $repo_build_path pull

docker compose -f $repo_build_path/docker-compose.yaml up -d --build
