#!/usr/bin/env bash

# Custom implementation of sg_maintenance.sh
# Original: https://github.com/sourcegraph/sourcegraph/blob/3.40/cmd/gitserver/server/sg_maintenance.sh
# Retrieved from customer Slack channel on 2024-12-13
# 
# The differences are:
# 1. This script can be stored in /home/sourcegraph on gitserver's volume,
# and executed from there
# 2. The path to the needed git repo can be passed in as a script parameter,
# ex. ~/sg_maintenance.sh /data/repos/perforce/repo
# 3. Most importantly, this script creates the SG_PAUSE and gc.pid lock files in the repo's directory,
# which should prevent Sourcegraph's background processes from running on the repo while this script is running,
# and git gc

set -euxo pipefail

REPOSITORY_FOLDER="${1:-""}"
if [ -z "${REPOSITORY_FOLDER}" ]; then
  echo "USAGE: $(basename "${BASH_SOURCE[0]}") [REPOSITORY_ROOT_FOLDER]"
  exit 1
fi
cd "$REPOSITORY_FOLDER"

declare -a files_to_cleanup

function cleanup() {
  for file in "${files_to_cleanup[@]}"; do
    rm "$file" || true
  done
}
trap cleanup EXIT

set -o noclobber

# pause all cleanup jobs, including garbage collection
echo "running sg maintenance manually" >SG_PAUSE

# cleanup the pause file once the script is done
files_to_cleanup+=("SG_PAUSE")

# set the 'git gc' pause file to prevent concurrent gc jobs
echo "1 $(hostname)" >.git/gc.pid

set +o noclobber

# try running 'git gc' (expecting to it fail) to confirm that our lock file works as expected
if git gc &>/dev/null; then
  echo "expected 'git gc' to fail, but it didn't. Please inspect the .git/gc.pid lockfile to confirm that it contains the correct contents."
  exit 1
fi

# cleanup the 'git gc' lock file once the script is done
files_to_cleanup+=(".git/gc.pid")

# Run sg_maintenance.sh steps from https://github.com/sourcegraph/sourcegraph/blob/3.40/cmd/gitserver/server/sg_maintenance.sh

# Usually run by git gc. Pack heads and tags for efficient repository access.
# --all Pack branch tips as well. Useful for a repository with many branches of
# historical interest.
git pack-refs --all --prune

# Usually run by git gc. The "expire" subcommand prunes older reflog entries.
# Entries older than expire time, or entries older than expire-unreachable time
# and not reachable from the current tip, are removed from the reflog.
# --all Process the reflogs of all references
git reflog expire --all

# Usually run by git gc. Here with the additional option --window-memory
# and --write-bitmap-index. We previously set the option --geometric=2, however
# this turned out to be too memory intensive for monorepos on some customer
# instances. Restricting the memory consumption by setting pack.windowMemory,
# pack.deltaCacheSize and pack.threads in addition to --geometric=2 seemed to
# have no effect.
git repack -d -l -A --write-bitmap-index --window-memory 100m --unpack-unreachable=now

# With the --changed-paths option, compute and write information about the
# paths changed between a commit and its first parent. This operation can take
# a while on large repositories. It provides significant performance gains for
# getting history of a directory or a file with git log -- <path>. If this
# option is given, future commit-graph writes will automatically assume that
# this option was intended
git commit-graph write --progress --reachable --changed-paths
