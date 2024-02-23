#!/usr/bin/env python3
# Python 3.12.1

### TODO:

    # Git SSH clone
        # Move git SSH clone from outside bash script into this script

    # Configure batch size, so we see repos in Sourcegraph update as the fetch jobs progress
        # git svn fetch --revision START:END
        # git svn fetch --revision BASE:[number]
            # to speed things along - so I recently added that as an answer to my own question (update now taking routinely less than an hour).  Still that all seemed really odd. "--revision" isn't documented as an option to "git svn fetch", you need to dig START out of .git/svn/.metadata and END out of the SVN repository.

    # When and how to change config parameters

        # Config parameters we want to support changing without having to docker compose down && docker compose up
            # Should be able to change / manage all config parameters without having to down && up

        # Config parameters we want to control remotely
            # Is changing these remotely sensible, especially if we don't have remote logging?

    # Parallelism
        # Poll the fetch process
            # Get the last line of output
            # To see if it's actually doing something, then log it
            # Output status update on clone jobs
                # Revision x of y completed, time taken, ETA for remaining revisions

    #.git ignore files
        # git svn create-ignore
        # git svn show-ignore
        # https://git-scm.com/docs/git-svn#Documentation/git-svn.txt-emcreate-ignoreem

    # Performance
        # --log-window-size

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
from pathlib import Path                                    # https://docs.python.org/3/library/pathlib.html
# import argparse                                             # https://docs.python.org/3/library/argparse.html
import json                                                 # https://docs.python.org/3/library/json.html
import logging                                              # https://docs.python.org/3/library/logging.html
import multiprocessing                                      # https://docs.python.org/3/library/multiprocessing.html
import os                                                   # https://docs.python.org/3/library/os.html
import shutil                                               # https://docs.python.org/3/library/shutil.html
import signal                                               # https://docs.python.org/3/library/signal.html
import subprocess                                           # https://docs.python.org/3/library/subprocess.html
import sys                                                  # https://docs.python.org/3/library/sys.html
import time                                                 # https://docs.python.org/3/library/time.html
# Third party libraries
# psutil requires adding gcc to the Docker image build, which adds about 4 minutes to the build time, and doubled the size of the image
# If there's a way to remove it, that may be handy
import psutil                                               # https://pypi.org/project/psutil/
import yaml                                                 # https://pyyaml.org/wiki/PyYAMLDocumentation


# Global variables
environment_variables_dict = {}
repos_dict = {}
script_name = os.path.basename(__file__)
script_run_number = 1


def register_signal_handler():

    logging.debug(f"Registering signal handler")

    try:

        signal.signal(signal.SIGINT, signal_handler)

    except Exception as exception:

        logging.error(f"Registering signal handler failed: {exception}")

    logging.debug(f"Registering signal handler succeeded")


def signal_handler(incoming_signal, frame):

    logging.debug(f"Received signal: {incoming_signal} frame: {frame}")

    signal_name = signal.Signals(incoming_signal).name

    logging.debug(f"Handled signal {signal_name}: {incoming_signal} frame: {frame}")


def load_config_from_environment_variables():

    # Try and read the environment variables from the Docker container's environment config
    # Set defaults in case they're not defined

    # DEBUG INFO WARNING ERROR CRITICAL
    environment_variables_dict['LOG_LEVEL']                         = os.environ.get("LOG_LEVEL", "DEBUG")
    environment_variables_dict['REPO_CONVERTER_INTERVAL_SECONDS']   = int(os.environ.get("REPO_CONVERTER_INTERVAL_SECONDS", 3600))
    # Path inside the container to find this file, only change to match if the right side of the volume mapping changes
    environment_variables_dict['REPOS_TO_CONVERT']                  = os.environ.get("REPOS_TO_CONVERT", "/sourcegraph/repos-to-convert.yaml")
    # Path inside the container to find this directory, only change to match if the right side of the volume mapping changes
    environment_variables_dict['SRC_SERVE_ROOT']                    = os.environ.get("SRC_SERVE_ROOT", "/sourcegraph/src-serve-root")


def load_config_from_repos_to_convert_file():
    # Try and load the environment variables from the REPOS_TO_CONVERT file


    # Check if the default config file exists
    # If yes, read configs from it
    # If no, use the environment variables
    pass


def configure_logging():

    logging.basicConfig(
        stream      = sys.stdout,
        datefmt     = "%Y-%m-%d %H:%M:%S",
        encoding    = "utf-8",
        format      = f"%(asctime)s; {script_name}; %(levelname)s; %(message)s",
        level       = environment_variables_dict['LOG_LEVEL']
    )


def parse_repos_to_convert_file_into_repos_dict():

    # The Python runtime seems to require this to get specified
    global repos_dict

    # Clear the dict for this execution to remove repos which have been removed from the yaml file
    repos_dict.clear()

    # Parse the repos-to-convert.yaml file
    try:

        # Open the file
        with open(environment_variables_dict['REPOS_TO_CONVERT'], "r") as repos_to_convert_file:

            # This should return a dict
            repos_dict = yaml.safe_load(repos_to_convert_file)
            # code_hosts_list_temp = yaml.safe_load(repos_to_convert_file)

            # # Weird thing we have to do
            # # Reading directory into repos_dict doesn't persist the dict outside the function
            # for repo_dict_key in code_hosts_list_temp.keys():

            #     # Store the repo_dict_key in the repos_dict
            #     repos_dict[repo_dict_key] = code_hosts_list_temp[repo_dict_key]

            logging.info(f"Parsed {len(repos_dict)} repos from {environment_variables_dict['REPOS_TO_CONVERT']}")

    except FileNotFoundError:

        logging.error(f"repos-to-convert.yaml file not found at {environment_variables_dict['REPOS_TO_CONVERT']}")
        sys.exit(1)

    except (AttributeError, yaml.scanner.ScannerError) as e:

        logging.error(f"Invalid YAML file format in {environment_variables_dict['REPOS_TO_CONVERT']}, please check the structure matches the format in the README.md. Exception: {type(e)}, {e.args}, {e}")
        sys.exit(2)


def clone_svn_repos():

    # Loop through the repos_dict, find the type: SVN repos, then add them to the dict of SVN repos
    for repo_key in repos_dict.keys():

        # If this repo isn't SVN, skip it
        if repos_dict[repo_key].get('type','').lower() != 'svn':
            continue

        # Get config parameters read from repos-to-clone.yaml, and set defaults if they're not provided
        git_repo_name           = repo_key
        svn_repo_code_root      = repos_dict[repo_key].get('svn-repo-code-root', None)
        username                = repos_dict[repo_key].get('username', None)
        password                = repos_dict[repo_key].get('password', None)
        code_host_name          = repos_dict[repo_key].get('code-host-name', None)
        git_org_name            = repos_dict[repo_key].get('git-org-name', None)
        git_default_branch      = repos_dict[repo_key].get('git-default-branch','main')
        fetch_batch_size        = repos_dict[repo_key].get('fetch-batch-size', None)
        repo_total_revisions    = repos_dict[repo_key].get('repo-total-revisions', None)
        authors_file_path       = repos_dict[repo_key].get('authors-file-path', None)
        authors_prog_path       = repos_dict[repo_key].get('authors-prog-path', None)
        git_ignore_file_path    = repos_dict[repo_key].get('git-ignore-file-path', None)
        layout                  = repos_dict[repo_key].get('layout', None)
        trunk                   = repos_dict[repo_key].get('trunk', None)
        tags                    = repos_dict[repo_key].get('tags', None)
        branches                = repos_dict[repo_key].get('branches', None)

        ## Parse config parameters into command args
        # TODO: Interpret code_host_name, git_org_name, and git_repo_name if not given
            # ex. https://svn.apache.org/repos/asf/parquet/site
            # code_host_name            = svn.apache.org    # can get by removing url scheme, if any, till the first /
            # arbitrary path on server  = repos             # optional, can either be a directory, or may actually be the repo
            # git_org_name              = asf
            # git_repo_name             = parquet
            # git repo root             = site              # arbitrary path inside the repo where contributors decided to start storing /trunk /branches /tags and other files to be included in the repo
        repo_path = str(environment_variables_dict['SRC_SERVE_ROOT']+"/"+code_host_name+"/"+git_org_name+"/"+git_repo_name)

        ## Define common command args
        arg_svn_non_interactive = [ "--non-interactive"                 ] # Do not prompt, just fail if the command doesn't work, only used for direct `svn` command
        arg_svn_username        = [ "--username", username              ]
        arg_svn_password        = [ "--password", password              ] # Only used for direct `svn` command
        # arg_svn_echo_password   = [ "echo", f"\"{password}\"", "|"      ] # Used for git svn commands # Breaks getting the correct process exit code
        arg_svn_echo_password   = None
        arg_svn_repo_code_root  = [ svn_repo_code_root                  ]
        arg_git_cfg             = [ "git", "-C", repo_path, "config"    ]
        arg_git_svn             = [ "git", "-C", repo_path, "svn"       ]

        ## Define commands
        cmd_run_svn_info            = [ "svn", "info"           ] + arg_svn_repo_code_root + arg_svn_non_interactive
        cmd_run_svn_log             = [ "svn", "log", "--xml"   ] + arg_svn_repo_code_root + arg_svn_non_interactive
        cmd_cfg_git_default_branch  = arg_git_cfg + [ "--global", "init.defaultBranch", git_default_branch ] # Possibility of collisions if multiple of these are run overlapping, make sure it's quick between reading and using this
        cmd_run_git_svn_init        = arg_git_svn + [ "init"                                ] + arg_svn_repo_code_root
        cmd_cfg_git_bare_clone      = arg_git_cfg + [ "core.bare", "true"                   ]
        cmd_cfg_git_authors_file    = arg_git_cfg + [ "svn.authorsfile", authors_file_path  ]
        cmd_cfg_git_authors_prog    = arg_git_cfg + [ "svn.authorsProg", authors_prog_path  ]
        cmd_run_git_svn_fetch       = arg_git_svn + [ "fetch"                               ]

        # Used to check if this command is already running in another process, without the password
        cmd_run_git_svn_fetch_without_password = ' '.join(cmd_run_git_svn_fetch)

        # States
            # Create:
                # State:
                    # The directory doesn't already exist
                    # The repo      doesn't already exist
                # How did we get here:
                    # First time - Create new path / repo / fetch job
                    # First run of the script
                    # New repo was added to the repos-to-convert.yaml file
                    # Repo was deleted from disk
                # Approach:
                    # Harder to test for the negative, so assume we're in the Create state, unless we find we're in the Running or Update states
        repo_state = "create"
            # Running:
                # State:
                    # An svn fetch process is still running
                # How did we get here:
                    # Fetch process is still running from a previous run of the script
                # Approach:
                    # Check first if the process is running, then continue this outer loop
            # Update:
                # State:
                    # Repo already exists, with a valid configuration
                # How did we get here:
                    # A fetch job was previously run, but is not currently running
                # Approach:
                    # Check if we're in the update state, then set repo_state = "update"
        # repo_state = "update"


        ## Check if we're in the Running state
        # Check if a fetch process is currently running for this repo
        try:

            ps_command = ["ps", "-e", "--format", "%a"]

            completed_ps_command = subprocess_run(ps_command)

            logging.debug(f"completed_ps_command: {completed_ps_command}")
            logging.debug(f"cmd_run_git_svn_fetch_without_password: {cmd_run_git_svn_fetch_without_password}")



            # git -C /sourcegraph/src-serve-root/subversion.noemalife.loc/vcs/las-halia.backend.ejb svn fetch --username svn.sourcegraph

            if cmd_run_git_svn_fetch_without_password in completed_ps_command:

                logging.info(f"Fetching process already running for {repo_key}")
                continue

        except Exception as e:
            logging.warning(f"Failed to check if {cmd_run_git_svn_fetch_without_password} is already running, will try to start it. Exception: {type(e)}, {e.args}, {e}")


        ## Check if we're in the Update state
        # Check if the git repo already exists and has the correct settings in the config file
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
                # So the url value is likely a substring, or a match of the svn_repo_code_root variable value
                # So we need to extract the url line, then check if it's in the svn_repo_code_root variable value
                for line in repo_git_config_file_contents.splitlines():

                    if "url =" in line:

                        # Get the URL value from the line
                        url_value = line.split("url = ")[1]

                        if url_value in svn_repo_code_root:
                            repo_state = "update"
                            logging.info(f"Found existing repo for {repo_key}, updating it")

                        # Break out of the inner for loop
                        break

        ## Modify commands based on config parameters
        if username:
            cmd_run_svn_info        += arg_svn_username
            cmd_run_svn_log         += arg_svn_username
            cmd_run_git_svn_init    += arg_svn_username
            cmd_run_git_svn_fetch   += arg_svn_username

        if password:
            arg_svn_echo_password   = True
            cmd_run_svn_info        += arg_svn_password
            cmd_run_svn_log         += arg_svn_password

        ## Run commands
        # Run the svn info command to test logging in to the SVN server, for network connectivity and credentials
        # Capture the output so we know the max revision in this repo's history
        svn_info = subprocess_run(cmd_run_svn_info, password, arg_svn_echo_password)

        if repo_state == "create":

            logging.info(f"Didn't find a repo on disk for {repo_key}, creating it")

            # # If the user didn't provide a batch size, try and determine one from repo stats
            # if not fetch_batch_size and not repo_total_revisions:

            #     # Get the rev number for the last rev this repo was changed from the svn info output
            #     # Default to not specifying a --revision
            #     if "Last Changed Rev:" in svn_info:

            #         last_changed_rev = int(svn_info.split("Last Changed Rev: ")[1].split(" ")[0])
            #         logging.debug(f"Last Changed Rev for {repo_key}: {last_changed_rev}")

            #         cmd_run_svn_log += ["--revision", "BASE:"+str(last_changed_rev)]

            #     # Get the number of revisions in this repo's history, to know how many batches to fetch in the initial clone
            #     # Note this could be a slow process
            #     svn_log = subprocess_run(cmd_run_svn_log, password)

            #     repo_rev_count = int(svn_info.split("Revision: ")[1].split(" ")[0])

            #     if repo_rev_count < 10000:
            #         fetch_batch_size = last_changed_rev
            #     else:
            #         fetch_batch_size = f"BASE:{last_changed_rev}"

            #     # TODO: Find a way to set batch size for initial fetch vs update fetches
            #     if fetch_batch_size and not fetch_batch_size == "HEAD":
            #         cmd_run_git_svn_fetch += ["--revision", fetch_batch_size]


            # Create the repo path if it doesn't exist
            if not os.path.exists(repo_path):
                os.makedirs(repo_path)

            # Set the default branch before init
            subprocess_run(cmd_cfg_git_default_branch)

            if layout:
                cmd_run_git_svn_init   += ["--stdlayout"]

                # Warn the user if they provided an invalid value for the layout, only standard is supported
                if "standard" not in layout and "std" not in layout:
                    logging.warning(f"Layout {layout} provided for repo {repo_key}, only standard is supported, continuing assuming standard")

            if trunk:
                cmd_run_git_svn_init   += ["--trunk", trunk]
            if tags:
                cmd_run_git_svn_init   += ["--tags", tags]
            if branches:
                cmd_run_git_svn_init   += ["--branches", branches]

            # Initialize the repo
            subprocess_run(cmd_run_git_svn_init, password, arg_svn_echo_password)

            # Configure the bare clone
            subprocess_run(cmd_cfg_git_bare_clone)



        ## Back to steps we do for both Create and Update states, so users can update the below parameters without having to restart the clone from scratch

        # Configure the authors file, if provided
        if authors_file_path:
            if os.path.exists(authors_file_path):
                subprocess_run(cmd_cfg_git_authors_file)
            else:
                logging.warning(f"Authors file not found at {authors_file_path}, skipping")

        # Configure the authors program, if provided
        if authors_prog_path:
            if os.path.exists(authors_prog_path):
                subprocess_run(cmd_cfg_git_authors_prog)
            else:
                logging.warning(f"Authors prog not found at {authors_prog_path}, skipping")

        # Configure the .gitignore file, if provided
        if git_ignore_file_path:
            if os.path.exists(git_ignore_file_path):
                logging.info(f"Copying .gitignore file from {git_ignore_file_path} to {repo_path}")
                shutil.copy2(git_ignore_file_path, repo_path)
            else:
                logging.warning(f".gitignore file not found at {git_ignore_file_path}, skipping")

        # Start a fetch
        logging.info(f"Fetching SVN repo {repo_key} with {cmd_run_git_svn_fetch_without_password}")

        # Retaining a reference to this process prevents the process from getting cleaned up automagically
        # But, removing all references to it doesn't seem to help it
        # So, need to keep a list and clean it up manually
        multiprocessing.Process(target=subprocess_run, name=f"subprocess_run({cmd_run_git_svn_fetch})", args=(cmd_run_git_svn_fetch, password, password)).start()


def redact_password_from_list(args, password=None):

    # AttributeError: 'list' object has no attribute 'replace'
    # Need to iterate through strings in list
    args_without_password = []

    if password:

        for arg in args:

            if password in arg:

                arg = arg.replace(password, "REDACTED-PASSWORD")

            args_without_password.append(arg)

    else:
        args_without_password = args.copy()

    return args_without_password


def subprocess_run(args, password=None, echo_password=None):

    # Redact passwords for logging
    # Convert to string because that's all we're using it for anyway
    args_without_password_string = ' '.join(redact_password_from_list(args, password))
    subprocess_stdout_and_stderr_without_password = None
    subprocess_stdout_without_password = None
    subprocess_stderr_without_password = None

    try:

        logging.debug(f"Starting subprocess: {args_without_password_string}")

        subprocess_to_run = psutil.Popen(
            args    = args,
            stdin   = subprocess.PIPE,
            stdout  = subprocess.PIPE,
            stderr  = subprocess.STDOUT,
            text    = True,
        )

        # If password is provided to this function, feed it into the subprocess' stdin pipe
        if echo_password:
            subprocess_stdout_and_stderr = subprocess_to_run.communicate(password)
        else:
            subprocess_stdout_and_stderr = subprocess_to_run.communicate()

        subprocess_stdout_and_stderr_without_password = redact_password_from_list(subprocess_stdout_and_stderr[0].splitlines(), password)

        if subprocess_to_run.returncode == 0:

            subprocess_stdout_without_password = subprocess_stdout_and_stderr_without_password
            logging.debug(f"Subprocess {subprocess_to_run} succeeded with stdout: {subprocess_stdout_without_password}")

        else:

            subprocess_stderr_without_password = subprocess_stdout_and_stderr_without_password
            logging.error(f"Subprocess {subprocess_to_run} failed with stderr: {subprocess_stderr_without_password}")

    except subprocess.CalledProcessError as error:
            logging.error(f"Subprocess {subprocess_to_run} raised exception: {error}")


    if subprocess_stderr_without_password:

        # Handle the case of abandoned git svn lock files blocking fetch processes
        # We already know that no other git svn fetch processes are running, because we checked for that before spawning this fetch process
        # fatal: Unable to create '/sourcegraph/src-serve-root/svn.apache.org/wsl/zest/.git/svn/refs/remotes/git-svn/index.lock': File exists.  Another git process seems to be running in this repository, e.g. an editor opened by 'git commit'. Please make sure all processes are terminated then try again. If it still fails, a git process may have crashed in this repository earlier: remove the file manually to continue. write-tree: command returned error: 128
        lock_file_error_strings = ["Unable to create", "index.lock", "File exists"]

        # Handle this as a string,
        stderr_without_password_string = " ".join(subprocess_stderr_without_password)
        lock_file_error_conditions = (lock_file_error_string in stderr_without_password_string for lock_file_error_string in lock_file_error_strings)
        if all(lock_file_error_conditions):

            try:

                # Get the index.lock file path from stderr_without_password_string
                lock_file_path = stderr_without_password_string.split("Unable to create '")[1].split("': File exists.")[0]

                logging.warning(f"Fetch failed to start due to finding a lockfile in repo at {lock_file_path}. Deleting the lockfile so it'll try again on the next run.")

                # Careful with recursive function call, don't create infinite recursion and fork bomb the container
                if subprocess_run(["rm", "-f", lock_file_path]):
                    logging.info(f"Successfully deleted {lock_file_path}")

            except subprocess.CalledProcessError as error:
                logging.error(f"Failed to rm -f lockfile at {lock_file_path} with error: {error}")

            except ValueError as error:
                logging.error(f"Failed to find git execution path in command args while trying to delete {lock_file_path} with error: {error}")

    return subprocess_stdout_without_password


def clone_tfs_repos():
    logging.warning("Cloning TFS repos function not implemented yet")

    # # Declare an empty dict for TFS repos to extract them from the repos_dict
    # tfs_repos_dict = {}

    # # Loop through the repos_dict, find the type: tfs repos, then add them to the dict of TFS repos
    # for repo_key in repos_dict.keys():

    #     repo_type = repos_dict[repo_key].get('type','').lower()

    #     if repo_type == 'tfs' or repo_type == 'tfvc':

    #         tfs_repos_dict[repo_key] = repos_dict[repo_key]


    # logging.info("Cloning TFS repos" + str(tfs_repos_dict))



def clone_git_repos():
    logging.warning("Cloning Git repos function not implemented yet")


def status_update_and_cleanup_zombie_processes():


    # subprocess_to_run = psutil.Popen(
    #     args    = args,
    #     stdin   = subprocess.PIPE,
    #     stdout  = subprocess.PIPE,
    #     stderr  = subprocess.STDOUT,
    #     text    = True,
    # )

    # Get the current process ID, should be 1 in Docker
    os_this_pid = os.getpid()

    # Using a set for built-in deduplication
    process_pids_to_wait_for = set()

    # Get a oneshot snapshot of all processes running this instant
    # Loop through for each processes
    for process in psutil.process_iter():

        # Get all upstream parent PIDs of the process
        process_parents_pids = [process_parent.pid for process_parent in process.parents()]

        # If this pid is in the parents, then we know its a child / grandchild / great-grandchild / etc. process of this process
        if os_this_pid in process_parents_pids:

            # Add the process' own PID to the set
            process_pids_to_wait_for.add(process.pid)

            # Loop through the process' parents and add them to the set too
            for process_parents_pid in process_parents_pids:

                process_pids_to_wait_for.add(process_parents_pid)

    # Remove this script's PID so it's not waiting on itself
    process_pids_to_wait_for.discard(os_this_pid)

    # Now that we have a set of all child / grandchild / etc PIDs without our own
    # Loop through them and wait for each one
    # If the process is a zombie, then waiting for it:
        # Gets the return value
        # Removes the process from the OS' process table
        # Raises an exception
    for process_pid_to_wait_for in process_pids_to_wait_for:

        try:

            # Create an instance of a Process object for the PID number
            # Raises psutil.NoSuchProcess if the PID has already finished
            process_to_wait_for = psutil.Process(process_pid_to_wait_for)

            # This rarely fires, ex. if cleaning up processes at the beginning of a script execution and the process finished during the interval
            if process_to_wait_for.status() == psutil.STATUS_ZOMBIE:
                logging.debug(f"Subprocess {process_to_wait_for} is a zombie")

            # Wait a short period, and capture the return status
            # Raises psutil.TimeoutExpired if the process is busy executing longer than the wait time
            return_status = process_to_wait_for.wait(0.1)

            logging.debug(f"Subprocess {process_pid_to_wait_for} finished now with return status: {return_status}")

        except psutil.NoSuchProcess as exception:
            logging.debug(f"Subprocess {process_pid_to_wait_for} already finished")

        except psutil.TimeoutExpired as exception:
            logging.debug(f"Subprocess {process_pid_to_wait_for} is still running at this moment")

        except Exception as exception:
            logging.debug(f"Subprocess {process_pid_to_wait_for} raised exception while waiting: {exception}")


def main():

    load_config_from_environment_variables()
    configure_logging()
    register_signal_handler()

    global script_run_number

    while True:

        load_config_from_repos_to_convert_file()
        logging.info(f"Starting {script_name} run {script_run_number} with args: " + str(environment_variables_dict))

        logging.debug("Multiprocessing module using start method: " + multiprocessing.get_start_method())
        status_update_and_cleanup_zombie_processes()

        cmd_cfg_git_safe_directory = ["git", "config", "--system", "--add", "safe.directory", "\"*\""]
        subprocess_run(cmd_cfg_git_safe_directory)

        parse_repos_to_convert_file_into_repos_dict()
        clone_svn_repos()
        # clone_tfs_repos()
        # clone_git_repos()

        status_update_and_cleanup_zombie_processes()

        logging.info(f"Finishing {script_name} run {script_run_number} with args: " + str(environment_variables_dict))

        # Sleep the configured interval
        logging.info(f"Sleeping for REPO_CONVERTER_INTERVAL_SECONDS={environment_variables_dict['REPO_CONVERTER_INTERVAL_SECONDS']} seconds")

        script_run_number += 1
        time.sleep(environment_variables_dict['REPO_CONVERTER_INTERVAL_SECONDS'])


if __name__ == "__main__":
    main()
