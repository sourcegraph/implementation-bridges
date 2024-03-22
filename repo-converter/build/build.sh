#!/bin/bash

set -o errexit

clear

pipreqs --force --mode gt .

export BUILD_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
export BUILD_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_DATE="$(date -u +'%Y-%m-%d %H:%M:%S')"
export BUILD_DIRTY="$(git diff --quiet && echo 'False' || echo 'True')"
export BUILD_TAG="$(git tag --points-at HEAD)"

docker compose up -d --build


if [ "$1" != "" ]
then

    clear

    docker compose logs repo-converter -f

fi
