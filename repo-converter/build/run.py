#!/usr/bin/env python3
# Python 3.12.1

### TODO:

    # Parallelism
            # Check its last line of output
            # Try calling the process to
                # Also clears out zombie processes
            # If not, script starts a new fetch job
                # Creates a lock file
                # Use the multiprocessing module to fork off a child process, but don't reuse the run_subprocess function, to avoid reference before assignment error of completed_process
            # Poll the fetch process
                # To see if it's completed, then log it
                # Output status update on clone jobs
                    # Revision x of y completed, time taken, ETA for remaining revisions
            # Store subprocess_dict in a file?

    # Configure batch size, so we see repos in Sourcegraph update as the fetch jobs progress
    # May be able to use
        # git config svn-remote.svn.branches-maxRev 590500


    # Test layout tags and branches as lists / arrays
    # Atlassian's Java binary to tidy up branches and tags

    # Delete repos from disk no longer in scope for the script?

### Notes:

    # Atlassian's SVN to Git migration guide
        # https://www.atlassian.com/git/tutorials/migrating-convert
        # Java script repo
        # https://marc-dev.sourcegraphcloud.com/bitbucket.org/atlassian/svn-migration-scripts/-/blob/src/main/scala/Authors.scala
        # Especially the Clean the new Git repository, to convert branches and tags
            # clean-git
            # java -Dfile.encoding=utf-8 -jar /sourcegraph/svn-migration-scripts.jar clean-git
            # Initial output looked good
            # Required a working copy
            # Didn't work
            # Corrupted repo

    # authors file
        # java -jar /sourcegraph/svn-migration-scripts.jar authors https://svn.apache.org/repos/asf/eagle > authors.txt
        # Kinda useful, surprisingly fast

    # git gc
        # Should be automatic?
        # Run the one from Atlassian's Jar file if needed

    # git default branch
        # Configure for the individual repo, before git init, so that it doesn't need to be set globally
        # for a bare repo git symbolic-ref HEAD refs/heads/trunk

    # git list all config
        # git -C $repo_path config --list

    # Find a python library for working with git repos programmatically instead of depending on git CLI
    # https://gitpython.readthedocs.io/en/stable/tutorial.html
        # Couple CVEs: https://nvd.nist.gov/vuln/search/results?query=gitpython

    # An example of doing the conversion in Python, not sure why when git svn exists
    # https://sourcegraph.com/github.com/gabrys/svn2github/-/blob/svn2github.py


## Import libraries
# Standard libraries
from multiprocessing import Process                         # https://docs.python.org/3/library/multiprocessing.html
from pathlib import Path                                    # https://docs.python.org/3/library/pathlib.html
import argparse                                             # https://docs.python.org/3/library/argparse.html
import json                                                 # https://docs.python.org/3/library/json.html
import logging                                              # https://docs.python.org/3/library/logging.html
import os                                                   # https://docs.python.org/3/library/os.html
import shutil                                               # https://docs.python.org/3/library/shutil.html
import subprocess                                           # https://docs.python.org/3/library/subprocess.html
import sys                                                  # https://docs.python.org/3/library/sys.html
import time                                                 # https://docs.python.org/3/library/time.html
# Third party libraries
# psutil requires adding gcc to the Docker image build, which adds about 4 minutes to the build time
import psutil                                               # https://pypi.org/project/psutil/
import yaml                                                 # https://pyyaml.org/wiki/PyYAMLDocumentation


# Global variables
script_name = os.path.basename(__file__)
args_dict = {}
repos_dict = {}


def parse_args():

    # Clear the global args_dict to ensure any args unset in this run get unset
    args_dict.clear()

    # Parse the command args
    parser = argparse.ArgumentParser(
        description     = "Clone TFS and SVN repos, convert them to Git, then serve them via src serve-git",
        usage           = f"Use {script_name} --help for more information",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--debug",
        action  = "store_true",
        default = False,
        help    = "Quick flag to set --log-level DEBUG",
    )
    parser.add_argument(
        "--repos-to-convert",
        default = "/sourcegraph/repos-to-convert.yaml",
        help    = "/sourcegraph/repos-to-convert.yaml file path, to read a list of TFS / SVN repos and access tokens to iterate through",
    )
    parser.add_argument(
        "--log-file",
        help    = "Log file path",
    )
    parser.add_argument(
        "--log-level",
        choices = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help    = "Log level",
    )
    parser.add_argument(
        "--quiet", "-q",
        action  = "store_true",
        help    = "Run without logging to stdout",
    )
    parser.add_argument(
        "--repo-share-path",
        default = "/sourcegraph/src-serve-root",
        help    = "Root of path to directory to store cloned Git repos",
    )
    parsed = parser.parse_args()

    # Store the parsed args in the args dictionary
    args_dict["repos_to_convert_file"]  = Path(parsed.repos_to_convert)
    args_dict["repo_share_path"]        = parsed.repo_share_path

    if parsed.quiet:
        args_dict["quiet"] = parsed.quiet

    if parsed.log_file:
        args_dict["log_file"] = Path(parsed.log_file)

    # Set the log level, in order of ascending precedence
    # Set the default, so this key isn't left empty
    args_dict["log_level"] = "INFO"

    # Override the default if defined in the OS environment variables
    if os.environ.get('LOG_LEVEL'):
        args_dict["log_level"] = os.environ.get('LOG_LEVEL')

    # Override the default and OS environment variables if specified in --log-level arg
    if parsed.log_level:
        args_dict["log_level"] = parsed.log_level

    # Override all if --debug provided
    if parsed.debug:
        args_dict["log_level"] = "DEBUG"


def set_logging():

    logging_handlers = []
    invalid_log_args = False

    # If the user provided a --log-file arg, then write to the file
    if "log_file" in args_dict.keys():
        logging_handlers.append(logging.FileHandler(args_dict["log_file"]))

    # If the user provided the --quiet arg, then don't write to stdout
    if "quiet" not in args_dict.keys():
        logging_handlers.append(logging.StreamHandler(sys.stdout))

    if len(logging_handlers) == 0:
        invalid_log_args = True
        logging_handlers.append(logging.StreamHandler(sys.stdout))


    logging.basicConfig(
        handlers    = logging_handlers,
        datefmt     = "%Y-%m-%d %H:%M:%S",
        encoding    = "utf-8",
        format      = f"%(asctime)s; {script_name}; %(levelname)s; %(message)s",
        level       = args_dict["log_level"]
    )

    if invalid_log_args:
        logging.critical(f"If --quiet is used to not print logs to stdout, then --log-file must be used to specify a log file. Invalid args: {args_dict}")
        sys.exit(1)


def parse_repos_to_convert_file_into_repos_dict():

    # Parse the repos-to-convert.yaml file
    try:

        # Open the file
        with open(args_dict["repos_to_convert_file"], "r") as repos_to_convert_file:

            # Returns a list, not a dict
            code_hosts_list_temp = yaml.safe_load(repos_to_convert_file)

            for repo_dict_key in code_hosts_list_temp.keys():

                # Store the repo_dict_key in the repos_dict
                repos_dict[repo_dict_key] = code_hosts_list_temp[repo_dict_key]

            logging.info(f"Parsed {len(repos_dict)} repos from {args_dict['repos_to_convert_file']}")

    except FileNotFoundError:

        logging.error(f"repos-to-convert.yaml file not found at {args_dict['repos_to_convert_file']}")
        sys.exit(1)

    except (AttributeError, yaml.scanner.ScannerError) as e:

        logging.error(f"Invalid YAML file format in {args_dict['repos_to_convert_file']}, please check the structure matches the format in the README.md. {type(e)}, {e.args}, {e}")
        sys.exit(2)


def clone_svn_repos():

    # Loop through the repos_dict, find the type: SVN repos, then add them to the dict of SVN repos
    for repo_key in repos_dict.keys():

        # If this repo isn't SVN, skip it
        if repos_dict[repo_key].get('type','').lower() != 'svn':
            continue

        # Get config parameters read from repos-to-clone.yaml
        svn_repo_code_root      = repos_dict[repo_key].get('svn-repo-code-root','')
        username                = repos_dict[repo_key].get('username','')
        password                = repos_dict[repo_key].get('password','')
        code_host_name          = repos_dict[repo_key].get('code-host-name','')
        git_org_name            = repos_dict[repo_key].get('git-org-name','')
        git_repo_name           = repos_dict[repo_key].get('git-repo-name','')
        git_default_branch      = repos_dict[repo_key].get('git-default-branch','main')
        authors_file_path       = repos_dict[repo_key].get('authors-file-path','')
        authors_prog_path       = repos_dict[repo_key].get('authors-prog-path','')
        git_ignore_file_path    = repos_dict[repo_key].get('git-ignore-file-path','')
        layout                  = repos_dict[repo_key].get('layout','')
        trunk                   = repos_dict[repo_key].get('trunk','')
        tags                    = repos_dict[repo_key].get('tags','')
        branches                = repos_dict[repo_key].get('branches','')

        ## Parse config parameters into command args
        # TODO: Interpret code_host_name, git_org_name, and git_repo_name if not given
        repo_path = str(args_dict["repo_share_path"]+"/"+code_host_name+"/"+git_org_name+"/"+git_repo_name)

        # States
        # repo_state = "create"
            # Create:
                # First time - Create new path / repo / fetch job
                # First run of the script
                # New repo was added to the repos-to-convert.yaml file
                # Repo was deleted from disk
        # repo_state = "update"
            # Update:
                # Not the first time
                # Repo already exists
                # A fetch job was previously started, and may or may not still be running

        # Assumptions
            # If the folder or repo don't already exist, then we're in the first time state

        # Check
            # If the git repo exists and has the correct settings in the config file, then it's not the first time

        # Assume we're in the Create state, unless the repo's git config file contains the svn repo url
        repo_state = "create"

        # If git config file exists for this repo, check if it contains the svn_repo_code_root value
        repo_git_config_file_path = repo_path + "/.git/config"

        if os.path.exists(repo_git_config_file_path):

            with open(repo_git_config_file_path, "r") as repo_git_config_file:

                repo_git_config_file_contents = repo_git_config_file.read()

                # It's not obvious in an SVN URL what's a server path, repo name, or repo path
                # SVN init checks the SVN remote's repo config, and stores the repo's URL in the.git/config file
                # [svn-remote "svn"]
                #       url = https://svn.apache.org/repos/asf
                #       fetch = ambari/trunk:refs/remotes/origin/trunk
                #       branches = ambari/branches/*:refs/remotes/origin/*
                #       tags = ambari/tags/*:refs/remotes/origin/tags/*
                # So we need to extract the url line, then check if it's in the svn_repo_code_root variable value

                for line in repo_git_config_file_contents.splitlines():

                    if "url =" in line:
                        # Get the URL value
                        url_value = line.split("url = ")[1]
                        if url_value in svn_repo_code_root:
                            repo_state = "update"
                            logging.info(f"Found existing repo for {repo_key}, updating it")
                        break

        ## Define common command args
        arg_svn_non_interactive = [ "--non-interactive"                 ] # Do not prompt, just fail if the command doesn't work, not supported by all commands
        arg_svn_username        = [ "--username", username              ]
        arg_svn_password        = [ "--password", password              ] # Only used for direct `svn` command
        arg_svn_echo_password   = [ "echo", password, "|"               ] # Used for git svn commands
        arg_svn_repo_code_root  = [ svn_repo_code_root                  ]
        arg_git_cfg             = [ "git", "-C", repo_path, "config"    ]
        arg_git_svn             = [ "git", "-C", repo_path, "svn"       ]

        ## Define commands
        cmd_svn_run_login           = [ "svn", "info" ] + arg_svn_repo_code_root + arg_svn_non_interactive
        cmd_git_cfg_default_branch  = arg_git_cfg + [ "--global", "init.defaultBranch", git_default_branch ] # Possibility of collisions if multiple of these are run overlapping, make sure it's quick between reading and using this
        cmd_git_run_svn_init        = arg_git_svn + [ "init"                                ] + arg_svn_repo_code_root
        cmd_git_cfg_bare_clone      = arg_git_cfg + [ "core.bare", "true"                   ]
        cmd_git_cfg_authors_file    = arg_git_cfg + [ "svn.authorsfile", authors_file_path  ]
        cmd_git_cfg_authors_prog    = arg_git_cfg + [ "svn.authorsProg", authors_prog_path  ]
        cmd_git_run_svn_fetch       = arg_git_svn + [ "fetch"                               ]

        # Used to check if this command is already running in another process, without the password
        cmd_git_run_svn_fetch_without_password = ' '.join(cmd_git_run_svn_fetch)

        ## Modify commands based on config parameters
        if username:
            cmd_git_run_svn_init   += arg_svn_username

        if password:
            cmd_git_run_svn_init    = arg_svn_echo_password + cmd_git_run_svn_init
            cmd_git_run_svn_fetch   = arg_svn_echo_password + cmd_git_run_svn_fetch

        if username and password:
            cmd_svn_run_login      += arg_svn_username + arg_svn_password

        if layout:
            cmd_git_run_svn_init   += ["--stdlayout"]

            # Warn the user if they provided an invalid value for the layout, only standard is supported
            if "standard" not in layout and "std" not in layout:
                logging.warning(f"Layout {layout} provided for repo {repo_key}, only standard is supported, continuing assuming standard")

        if trunk:
            cmd_git_run_svn_init   += ["--trunk", trunk]
        if tags:
            cmd_git_run_svn_init   += ["--tags", tags]
        if branches:
            cmd_git_run_svn_init   += ["--branches", branches]

        ## Run commands
        # Log in to the SVN server to test if credentials are needed / provided / valid
        subprocess_run(cmd_svn_run_login, password)

        if repo_state == "create":

            # Create the repo path if it doesn't exist
            if not os.path.exists(repo_path):
                os.makedirs(repo_path)

            # Set the default branch before init
            subprocess_run(cmd_git_cfg_default_branch)

            # Initialize the repo
            subprocess_run(cmd_git_run_svn_init, password)

            # Configure the bare clone
            subprocess_run(cmd_git_cfg_bare_clone)

            # Configure the authors file, if provided
            if authors_file_path:
                if os.path.exists(authors_file_path):
                    subprocess_run(cmd_git_cfg_authors_file)
                else:
                    logging.warning(f"Authors file not found at {authors_file_path}, skipping")

            # Configure the authors program, if provided
            if authors_prog_path:
                if os.path.exists(authors_prog_path):
                    subprocess_run(cmd_git_cfg_authors_prog)
                else:
                    logging.warning(f"Authors prog not found at {authors_prog_path}, skipping")

            # Configure the .gitignore file, if provided
            if git_ignore_file_path:
                if os.path.exists(git_ignore_file_path):
                    logging.debug(f"Copying .gitignore file from {git_ignore_file_path} to {repo_path}")
                    shutil.copy2(git_ignore_file_path, repo_path)
                else:
                    logging.warning(f".gitignore file not found at {git_ignore_file_path}, skipping")

        try:

            # Check if any running process has the git svn fetch command in it
            running_processes = {}
            for process in psutil.process_iter():

                process_command = ' '.join(process.cmdline())
                running_processes[process_command] = process.pid

            # If yes, continue
            # It'd be much easier to run this check directly in the above loop, but then the continue would just break out of the inner loop, and not skip the repo
            if cmd_git_run_svn_fetch_without_password in running_processes.keys():
                pid = running_processes[cmd_git_run_svn_fetch_without_password]
                process = psutil.Process(pid)
                process_command = ' '.join(process.cmdline())
                logging.debug(f"Found pid {pid} running, skipping git svn fetch. Process: {process}, Command: {process_command}")
                continue

        except Exception as e:
            logging.warning(f"Failed to check if {cmd_git_run_svn_fetch_without_password} is already running, will try to start it. Exception: {e}")

        # Start a fetch
        logging.info(f"Fetching SVN repo {repo_key} with {cmd_git_run_svn_fetch_without_password}")
        git_svn_fetch(cmd_git_run_svn_fetch, password)


def git_svn_fetch(cmd_git_run_svn_fetch, password):

    fetch_process = Process(target=subprocess_run, args=(cmd_git_run_svn_fetch, password))
    fetch_process.start()

    return fetch_process.pid


def subprocess_run(args, password=False):

    # Using the subprocess module
    # https://docs.python.org/3/library/subprocess.html#module-subprocess
    # Waits for the process to complete

    # Redact passwords for logging
    args_without_password = args.copy()
    if password:
        args_without_password[args_without_password.index(password)] = "REDACTED-PASSWORD"

    try:

        logging.debug(f"Starting subprocess: {' '.join(args_without_password)}")

        completed_process = subprocess.run(args, check=True, capture_output=True, text=True)

        if completed_process.returncode == 0:
            logging.debug(f"Subprocess succeeded: {' '.join(args_without_password)} with output: {completed_process.stdout}")

    except subprocess.CalledProcessError as error:

        logging.error(f"Subprocess failed: {' '.join(args_without_password)} with error: {error}, and stderr: {error.stderr}")


def clone_tfs_repos():

    # Declare an empty dict for TFS repos to extract them from the repos_dict
    tfs_repos_dict = {}

    # Loop through the repos_dict, find the type: tfs repos, then add them to the dict of TFS repos
    for repo_key in repos_dict.keys():

        repo_type = repos_dict[repo_key].get('type','').lower()

        if repo_type == 'tfs' or repo_type == 'tfvc':

            tfs_repos_dict[repo_key] = repos_dict[repo_key]


    logging.debug("Cloning TFS repos" + str(tfs_repos_dict))


def cleanup_zombie_processes():

    logging.debug("Checking for zombie processes")

    # Get a list of all the running processes
    pid_list = psutil.pids()
    for pid in pid_list:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                logging.debug(f"Found zombie process {pid}, trying to flush it from the proc table")
                psutil.Process(pid).wait(0)

        except Exception as e:
            logging.debug(f"Failed while checking for zombie processes, exception: {type(e)}, {e.args}, {e}")


def main():

    # Run every 60 minutes by default
    run_interval_seconds = os.environ.get('BRIDGE_REPO_CONVERTER_INTERVAL_SECONDS', 3600)
    run_number = 0

    while True:


        parse_args()
        set_logging()
        logging.debug(f"Starting {script_name} run {run_number} with args: " + str(args_dict))

        cleanup_zombie_processes()

        parse_repos_to_convert_file_into_repos_dict()
        clone_svn_repos()
        # clone_tfs_repos()

        logging.debug(f"Finishing {script_name} run {run_number} with args: " + str(args_dict))
        logging.debug(f"Sleeping for BRIDGE_REPO_CONVERTER_INTERVAL_SECONDS={run_interval_seconds} seconds")
        run_number += 1

        # Sleep the configured interval
        time.sleep(int(run_interval_seconds))


if __name__ == "__main__":
    main()
