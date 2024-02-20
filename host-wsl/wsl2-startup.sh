#!/bin/bash
# Use a setup like this: https://iknowthatnow.com/2022/04/04/start-wsl2-services-on-windows-startup/

log_file="./log"
git_exit_status=""
docker_compose_exit_status=""
repo_build_path="/sourcegraph/implementation-bridges/repo-converter/build"

echo "Starting $0 $@" >> $log_file

# Git pull latest commits to main
if ! git -C $repo_build_path pull
then
    git_exit_status=$?
    echo "git pull failed, exit code $git_exit_status" >> $log_file
    exit $git_exit_status
fi

# Start docker compose services
if ! docker compose -f $repo_build_path/docker-compose.yaml up -d --build
then
    docker_compose_exit_status=$?
    echo "docker compose up failed, exit code $docker_compose_exit_status" >> $log_file
    exit $docker_compose_exit_status
fi


echo "Finishing $0 $@" >> $log_file
