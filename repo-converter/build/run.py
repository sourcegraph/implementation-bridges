#!/usr/bin/env python3
# Python 3.12.1

### TODO:

    # Definition of Done:
        # Git - Done enough for PoC, running as a cronjob on the customer's Linux VM
        # SVN - Need to sort out branches
        # TFVC - Need to sort out branches

    # Git

        # SSH clone
            # Move git SSH clone from outside bash script into this script

    # TFVC

        # Convert tfs-to-git Bash script to Python and add it here

    # SVN

        # Branches
            # Problem
                # Sort out how to see all branches in Sourcegraph
            # Approaches
                # Can we accomplish the same with a bare clone, or do we need a working copy for git reasons?
                    # for a bare repo: git symbolic-ref HEAD refs/heads/trunk
                # Do we need a Python Git library to modify the repo metadata (may be safer, if the library uses lock files?), or can we do it as a file-based operation?
                # Atlassian's Java binary to tidy up branches and tags?

        # Parallelism
            # Add a max concurrent repos environment variable

        # SVN commands hanging
            # Add a timeout for hanging svn info and svn log commands, if data isn't transferring

        # .gitignore files
            # git svn create-ignore
            # git svn show-ignore
            # https://git-scm.com/docs/git-svn#Documentation/git-svn.txt-emcreate-ignoreem

        # Test layout tags and branches as lists / arrays

        # Run git svn log --xml to store the repo's log on disk, then append to it when there are new revisions, so getting counts of revisions in each repo is slow once, fast many times

### Notes:

    # psutil requires adding gcc to the Docker image build, which adds 4 minutes to the build time, and doubles the image size
    # It would be handy if there was a workaround without it, but multiprocessing.active_children() doesn't join the intermediate processes that Python forks

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

    # git default branch for init / initial clone
        # Find a way to configure it for each repo, before or after git init, so that it doesn't need to be set globally, risk collisions

    # git list all config
        # git -C $local_repo_path config --list

    # Find a python library for working with git repos programmatically instead of depending on git CLI
    # https://gitpython.readthedocs.io/en/stable/tutorial.html
        # Couple CVEs: https://nvd.nist.gov/vuln/search/results?query=gitpython

    # An example of doing the conversion in Python, not sure why when git svn exists
    # https://sourcegraph.com/github.com/gabrys/svn2github/-/blob/svn2github.py


## Import libraries
# Standard libraries
from pathlib import Path                                    # https://docs.python.org/3/library/pathlib.html
import json                                                 # https://docs.python.org/3/library/json.html
import logging                                              # https://docs.python.org/3/library/logging.html
import multiprocessing                                      # https://docs.python.org/3/library/multiprocessing.html
import os                                                   # https://docs.python.org/3/library/os.html
import random                                               # https://docs.python.org/3/library/random.html
import shutil                                               # https://docs.python.org/3/library/shutil.html
import signal                                               # https://docs.python.org/3/library/signal.html
import subprocess                                           # https://docs.python.org/3/library/subprocess.html
import sys                                                  # https://docs.python.org/3/library/sys.html
import textwrap                                             # https://docs.python.org/3/library/textwrap.html
import time                                                 # https://docs.python.org/3/library/time.html
import traceback                                            # https://docs.python.org/3/library/traceback.html
# Third party libraries
import psutil                                               # https://pypi.org/project/psutil/
import yaml                                                 # https://pyyaml.org/wiki/PyYAMLDocumentation


# Global variables
environment_variables_dict = {}
git_config_namespace = "repo-converter"
repos_dict = {}
script_name = os.path.basename(__file__)
script_run_number = 1


def register_signal_handler():

    try:

        signal.signal(signal.SIGINT, signal_handler)

    except Exception as exception:

        logging.error(f"Registering signal handler failed with exception: {type(exception)}, {exception.args}, {exception}")


def signal_handler(incoming_signal, frame):

    logging.debug(f"Received signal: {incoming_signal} frame: {frame}")

    signal_name = signal.Signals(incoming_signal).name

    logging.debug(f"Handled signal {signal_name}: {incoming_signal} frame: {frame}")


def load_config_from_environment_variables():

    # Try and read the environment variables from the Docker container's environment config
    # Set defaults in case they're not defined

    # DEBUG INFO WARNING ERROR CRITICAL
    environment_variables_dict["LOG_LEVEL"]                         = os.environ.get("LOG_LEVEL", "DEBUG")
    environment_variables_dict["REPO_CONVERTER_INTERVAL_SECONDS"]   = int(os.environ.get("REPO_CONVERTER_INTERVAL_SECONDS", 3600))
    # Path inside the container to find this file, only change to match if the right side of the volume mapping changes
    environment_variables_dict["REPOS_TO_CONVERT"]                  = os.environ.get("REPOS_TO_CONVERT", "/sourcegraph/repos-to-convert.yaml")
    # Path inside the container to find this directory, only change to match if the right side of the volume mapping changes
    environment_variables_dict["SRC_SERVE_ROOT"]                    = os.environ.get("SRC_SERVE_ROOT", "/sourcegraph/src-serve-root")


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
        level       = environment_variables_dict["LOG_LEVEL"]
    )


def git_config_safe_directory():

    cmd_git_safe_directory = ["git", "config", "--system", "--replace-all", "safe.directory", "\"*\""]
    subprocess_run(cmd_git_safe_directory)


def parse_repos_to_convert_file_into_repos_dict():

    # The Python runtime seems to require this to get specified
    global repos_dict

    # Clear the dict for this execution to remove repos which have been removed from the yaml file
    repos_dict.clear()

    # Parse the repos-to-convert.yaml file
    try:

        # Open the file
        with open(environment_variables_dict["REPOS_TO_CONVERT"], "r") as repos_to_convert_file:

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

    except (AttributeError, yaml.scanner.ScannerError) as exception:

        logging.error(f"Invalid YAML file format in {environment_variables_dict['REPOS_TO_CONVERT']}, please check the structure matches the format in the README.md. Exception: {type(exception)}, {exception.args}, {exception}")
        sys.exit(2)


def clone_svn_repos():

    # Loop through the repos_dict, find the type: SVN repos, then fork off a process to clone them
    for repo_key in repos_dict.keys():

        repo_type = repos_dict[repo_key].get("type","").lower()

        if "svn" in repo_type or "subversion" in repo_type:

            multiprocessing.Process(target=clone_svn_repo, name=f"clone_svn_repo_{repo_key}", args=(repo_key,)).start()


def clone_svn_repo(repo_key):

    # Get config parameters read from repos-to-clone.yaml, and set defaults if they're not provided
    git_repo_name               = repo_key
    authors_file_path           = repos_dict[repo_key].get("authors-file-path", None)
    authors_prog_path           = repos_dict[repo_key].get("authors-prog-path", None)
    bare_clone                  = repos_dict[repo_key].get("bare-clone", True)
    branches                    = repos_dict[repo_key].get("branches", None)
    code_host_name              = repos_dict[repo_key].get("code-host-name", None)
    fetch_batch_size            = repos_dict[repo_key].get("fetch-batch-size", 100)
    git_default_branch          = repos_dict[repo_key].get("git-default-branch","trunk")
    git_ignore_file_path        = repos_dict[repo_key].get("git-ignore-file-path", None)
    git_org_name                = repos_dict[repo_key].get("git-org-name", None)
    layout                      = repos_dict[repo_key].get("layout", None)
    password                    = repos_dict[repo_key].get("password", None)
    svn_remote_repo_code_root   = repos_dict[repo_key].get("svn-repo-code-root", None)
    tags                        = repos_dict[repo_key].get("tags", None)
    trunk                       = repos_dict[repo_key].get("trunk", None)
    username                    = repos_dict[repo_key].get("username", None)

    ## Parse config parameters into command args
    # TODO: Interpret code_host_name, git_org_name, and git_repo_name if not given
        # ex. https://svn.apache.org/repos/asf/parquet/site
        # code_host_name            = svn.apache.org    # can get by removing url scheme, if any, till the first /
        # arbitrary path on server  = repos             # optional, can either be a directory, or may actually be the repo
        # git_org_name              = asf
        # git_repo_name             = parquet
        # git repo root             = site              # arbitrary path inside the repo where contributors decided to start storing /trunk /branches /tags and other files to be included in the repo
    local_repo_path = str(environment_variables_dict["SRC_SERVE_ROOT"]+"/"+code_host_name+"/"+git_org_name+"/"+git_repo_name)

    ## Define common command args
    arg_batch_end_revision          =           [ f"{git_config_namespace}.batch-end-revision"  ]
    arg_git                         =           [ "git", "-C", local_repo_path                  ]
    arg_git_cfg                     = arg_git + [ "config"                                      ]
    arg_git_svn                     = arg_git + [ "svn"                                         ]
    arg_svn_echo_password           = None
    arg_svn_non_interactive         =           [ "--non-interactive"                           ] # Do not prompt, just fail if the command doesn't work, only used for direct `svn` command
    arg_svn_password                =           [ "--password", password                        ] # Only used for direct `svn` commands
    arg_svn_remote_repo_code_root   =           [ svn_remote_repo_code_root                     ]
    arg_svn_username                =           [ "--username", username                        ]

    ## Define commands
    # One offs in the new array
    # Reused one in their own arrays above, even if they're single element arrays
    cmd_git_authors_file            = arg_git_cfg + [ "svn.authorsfile", authors_file_path                  ]
    cmd_git_authors_prog            = arg_git_cfg + [ "svn.authorsProg", authors_prog_path                  ]
    cmd_git_bare_clone              = arg_git_cfg + [ "core.bare", "true"                                   ]
    cmd_git_default_branch          = arg_git_cfg + [ "--global", "init.defaultBranch", git_default_branch  ] # Possibility of collisions if multiple of these are run overlapping, make sure it's quick between reading and using this
    cmd_git_get_batch_end_revision  = arg_git_cfg + [ "--get"                                               ] + arg_batch_end_revision
    cmd_git_get_svn_url             = arg_git_cfg + [ "--get", "svn-remote.svn.url"                         ]
    cmd_git_set_batch_end_revision  = arg_git_cfg + [ "--replace-all"                                       ] + arg_batch_end_revision
    cmd_git_svn_fetch               = arg_git_svn + [ "fetch"                                               ]
    cmd_git_svn_init                = arg_git_svn + [ "init"                                                ] + arg_svn_remote_repo_code_root
    cmd_svn_info                    =               [ "svn", "info"                                         ] + arg_svn_non_interactive + arg_svn_remote_repo_code_root
    cmd_svn_log                     =               [ "svn", "log", "--xml", "--with-no-revprops"           ] + arg_svn_non_interactive + arg_svn_remote_repo_code_root

    ## Modify commands based on config parameters
    if username:
        cmd_svn_info        += arg_svn_username
        cmd_svn_log         += arg_svn_username
        cmd_git_svn_init    += arg_svn_username
        cmd_git_svn_fetch   += arg_svn_username

    if password:
        arg_svn_echo_password   = True
        cmd_svn_info        += arg_svn_password
        cmd_svn_log         += arg_svn_password

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

    # Check if a fetch or log process is currently running for this repo
    try:

        # Get running processes, both as a list and string
        ps_command = ["ps", "--no-headers", "-e", "--format", "pid,args"]
        running_processes = subprocess_run(ps_command)["output"]
        running_processes_string        = " ".join(running_processes)

        # Define the list of strings we're looking for in the running processes' commands
        cmd_git_svn_fetch_string    = " ".join(cmd_git_svn_fetch)
        cmd_svn_log_string          = " ".join(cmd_svn_log)
        process_name                    = f"clone_svn_repo_{repo_key}"
        log_failure_message             = ""

        # In priority order
        concurrency_error_strings_and_messages = [
            (process_name,                  "previous process still running"         ),
            (cmd_git_svn_fetch_string,      "previous fetching process still running"),
            (cmd_svn_log_string,            "previous svn log process still running" ),
            (local_repo_path,               "local repo path in process running"     ), # Problem: if one repo's name is a substring of another repo's name
            # (svn_remote_repo_code_root,     "repo url in process running"            ), # Problem: Multiple clones from the same URL
        ]

        # Loop through the list of strings we're looking for, to check the running processes for each of them
        for concurrency_error_string_and_message in concurrency_error_strings_and_messages:

            # If this string we're looking for is found
            if concurrency_error_string_and_message[0] in running_processes_string:

                # Find which process it's in
                for running_process in running_processes:
                    pid, args = running_process.lstrip().split(" ", 1)

                    # If it's this process, and this process hasn't already matched one of the previous concurrency errors
                    if (
                        concurrency_error_string_and_message[0] in args and
                        pid not in log_failure_message
                    ):

                        # Add its message to the string
                        log_failure_message += f"{concurrency_error_string_and_message[1]} in pid {pid}, command {args}, "

                        # Could use something like this to try and find the process name
                        # multiprocessing.Process(target=clone_svn_repo, name=f"clone_svn_repo_{repo_key}", args=(repo_key,)).start()
                        # name=f"clone_svn_repo_{repo_key}" shows up in exception stack traces, need to figure out where to find it
                        # try:

                        #     process_name = psutil.Process(int(pid)).name()

                        #     if process_name:
                        #         log_failure_message += f"process name: {process_name}, "

                        # except psutil.NoSuchProcess as exception:
                        #     pass

        if log_failure_message:
            logging.info(f"{repo_key}; {log_failure_message}skipping")
            return

    except FileNotFoundError as exception:
        # FileNotFoundError: [Errno 2] No such file or directory: '/proc/69/cwd'
        # Running ps can fail trying to find process data in the proc table
        # Safe to ignore in this case
        pass

    except Exception as exception:

        # repo-converter  | 2024-03-14 10:46:41; run.py; WARNING; ant; Failed to check if fetching process is already running, will try to start it.
        # Exception: <class 'FileNotFoundError'>, (2, 'No such file or directory'), [Errno 2] No such file or directory: '/proc/16/cwd'
        logging.warning(f"{repo_key}; Failed to check if fetching process is already running, will try to start it. Exception: {type(exception)}, {exception.args}, {exception}")

        stack = traceback.extract_stack()
        (filename, line, procname, text) = stack[-1]

        logging.warning(f"filename, line, procname, text: {filename, line, procname, text}")

        raise exception

    ## Check if we're in the Update state
    # Check if the git repo already exists and has the correct settings in the config file
    try:

        svn_remote_url = subprocess_run(cmd_git_get_svn_url, quiet=True)["output"][0]

        if svn_remote_url in svn_remote_repo_code_root:

            repo_state = "update"

    except TypeError as exception:
        # Get an error when trying to git config --get svn-remote.svn.url, when the directory doesn't exist on disk
        # WARNING; karaf; failed to check git config --get svn-remote.svn.url. Exception: <class 'TypeError'>, ("'NoneType' object is not subscriptable",), 'NoneType' object is not subscriptable
        logging.warning(f"{repo_key}; failed to check git config --get svn-remote.svn.url. Exception: {type(exception)}, {exception.args}, {exception}")

    except Exception as exception:
        logging.warning(f"{repo_key}; failed to check git config --get svn-remote.svn.url. Exception: {type(exception)}, {exception.args}, {exception}")


    ## Run commands
    # Run the svn info command to test logging in to the SVN server, for network connectivity and credentials
    # Capture the output so we know the max revision in this repo's history
    svn_info = subprocess_run(cmd_svn_info, password, arg_svn_echo_password)
    svn_info_output_string = " ".join(svn_info["output"])

    if svn_info["returncode"] != 0:

        # The clone_svn_repo function runs in its own process, get this process' start time
        # Check for current time < start time + REPO_CONVERTER_INTERVAL_SECONDS, to ensure that this retry is not extending beyond the interval
        process_create_time = psutil.Process(os.getpid()).create_time()

        # Let it retry up top 80% of the time remaining until the next REPO_CONVERTER_INTERVAL_SECONDS, so this process doesn't overrun the current interval
        retry_time_limit = process_create_time + int(environment_variables_dict["REPO_CONVERTER_INTERVAL_SECONDS"] * 0.8)

        # Set a maximum retry delay of one third of REPO_CONVERTER_INTERVAL_SECONDS, so it can retry 2-3 times, or 60 seconds, whichever is shorter
        retry_delay_range = min(int(environment_variables_dict["REPO_CONVERTER_INTERVAL_SECONDS"] / 3), 60)

        # Set a maximum number of retries per script run
        retry_attempts_max  = 3
        retries_attempted   = 0

        svn_connection_failure_message_to_check_for = "Unable to connect to a repository at"

        while (
            svn_connection_failure_message_to_check_for in svn_info_output_string and
            time.time() < retry_time_limit and
            retries_attempted < retry_attempts_max
        ):

            retries_attempted += 1
            retry_delay_seconds = random.randrange(1, retry_delay_range)

            logging.warning(f"{repo_key}; Failed to connect to repo remote, retrying {retries_attempted} of max {retry_attempts_max} times, with a semi-random delay of {retry_delay_seconds} seconds")

            time.sleep(retry_delay_seconds)

            svn_info = subprocess_run(cmd_svn_info, password, arg_svn_echo_password)
            svn_info_output_string = " ".join(svn_info["output"])

        if svn_info["returncode"] != 0:

            log_failure_message = ""

            if retries_attempted == retry_attempts_max:
                log_failure_message = f"hit retry count limit {retry_attempts_max} for this run"

            elif not time.time() < retry_time_limit:
                log_failure_message = f"hit retry time limit for this run"

            logging.error(f"{repo_key}; Failed to connect to repo remote, {log_failure_message}, skipping")
            return

        else:

            logging.warning(f"{repo_key}; Successfully connected to repo remote after {retries_attempted} retries")

    # Get last changed revision for this repo
    last_changed_rev = svn_info_output_string.split("Last Changed Rev: ")[1].split(" ")[0]

    # Check if the previous batch end revision is the same as the last changed rev from svn info
    # If yes, we're up to date, return to the next repo, instead of forking the git svn process to do the same check
    if repo_state == "update":

        #  TypeError: 'NoneType' object is not subscriptable
        try:
            previous_batch_end_revision = subprocess_run(cmd_git_get_batch_end_revision)["output"][0]
        except Exception as exception:
            previous_batch_end_revision = "1"

        if previous_batch_end_revision == last_changed_rev:

            logging.info(f"{repo_key}; up to date, skipping; local rev {previous_batch_end_revision}, remote rev {last_changed_rev}")
            return

        else:

            cmd_svn_log_remaining_revs = cmd_svn_log + ["--revision", f"{previous_batch_end_revision}:HEAD"]
            svn_log_remaining_revs = subprocess_run(cmd_svn_log_remaining_revs, password, arg_svn_echo_password)["output"]
            svn_log_remaining_revs_string = " ".join(svn_log_remaining_revs)
            remaining_revs = svn_log_remaining_revs_string.count("revision=")
            logging.info(f"{repo_key}; out of date; local rev {previous_batch_end_revision}, remote rev {last_changed_rev}, {remaining_revs} revs remaining to catch up, fetching next batch of {min(remaining_revs,fetch_batch_size)} revisions")


    if repo_state == "create":

        logging.info(f"{repo_key}; didn't find a local clone, creating one")

        # Create the repo path if it doesn't exist
        if not os.path.exists(local_repo_path):
            os.makedirs(local_repo_path)

        # Set the default branch before init
        subprocess_run(cmd_git_default_branch)

        if layout:
            cmd_git_svn_init   += ["--stdlayout"]

            # Warn the user if they provided an invalid value for the layout, only standard is supported
            if "standard" not in layout and "std" not in layout:
                logging.warning(f"{repo_key}; Layout shortcut provided with incorrect value {layout}, only standard is supported for the shortcut, continuing assuming standard, otherwise provide --trunk, --tags, and --branches")

        if trunk:
            cmd_git_svn_init   += ["--trunk", trunk]
        if tags:
            cmd_git_svn_init   += ["--tags", tags]
        if branches:
            cmd_git_svn_init   += ["--branches", branches]

        # Initialize the repo
        subprocess_run(cmd_git_svn_init, password, arg_svn_echo_password)

        # Initialize this config with a 0 value
        cmd_git_set_batch_end_revision.append(str(0))
        subprocess_run(cmd_git_set_batch_end_revision)

        # Configure the bare clone
        # Testing without the bare clone to see if branching works easier
        # and because I forget why a bare clone was needed
        if bare_clone:
            subprocess_run(cmd_git_bare_clone)


    ## Back to steps we do for both Create and Update states, so users can update the below parameters without having to restart the clone from scratch
    # TODO: Check if these configs are already set the same before trying to set them

    # Configure the authors file, if provided
    if authors_file_path:
        if os.path.exists(authors_file_path):
            subprocess_run(cmd_git_authors_file)
        else:
            logging.warning(f"{repo_key}; authors file not found at {authors_file_path}, skipping configuring it")

    # Configure the authors program, if provided
    if authors_prog_path:
        if os.path.exists(authors_prog_path):
            subprocess_run(cmd_git_authors_prog)
        else:
            logging.warning(f"{repo_key}; authors prog not found at {authors_prog_path}, skipping configuring it")

    # Configure the .gitignore file, if provided
    if git_ignore_file_path:
        if os.path.exists(git_ignore_file_path):
            shutil.copy2(git_ignore_file_path, local_repo_path)
        else:
            logging.warning(f"{repo_key}; .gitignore file not found at {git_ignore_file_path}, skipping configuring it")

    # Batch processing
    batch_start_revision    = None
    batch_end_revision      = None

    try:

        # Get the revision number to start with
        if repo_state == "update":

            # Try to retrieve repo-converter.batch-end-revision from git config
            # previous_batch_end_revision = git config --get repo-converter.batch-end-revision
            # Need to fail gracefully
            previous_batch_end_revision = subprocess_run(cmd_git_get_batch_end_revision)["output"]

            if previous_batch_end_revision:

                batch_start_revision = int(" ".join(previous_batch_end_revision)) + 1

        if repo_state == "create" or batch_start_revision == None:

            # If this is a new repo, get the first changed revision number for this repo from the svn server log
            cmd_svn_log_batch_start_revision = cmd_svn_log + ["--limit", "1", "--revision", "1:HEAD"]
            svn_log_batch_start_revision = subprocess_run(cmd_svn_log_batch_start_revision, password, arg_svn_echo_password)["output"]
            batch_start_revision = int(" ".join(svn_log_batch_start_revision).split("revision=\"")[1].split("\"")[0])

        # Get the revision number to end with
        if batch_start_revision:

            # Get the batch size'th revision number for the rev to end this batch range
            cmd_svn_log_batch_end_revision = cmd_svn_log + ["--limit", str(fetch_batch_size), "--revision", f"{batch_start_revision}:HEAD"]
            cmd_svn_log_batch_end_revision_output = subprocess_run(cmd_svn_log_batch_end_revision, password, arg_svn_echo_password)["output"]

            try:

                # While we're at it, update the batch starting rev to the first real rev number after the previous end rev +1
                batch_start_revision = int(" ".join(cmd_svn_log_batch_end_revision_output).split("revision=\"")[1].split("\"")[0])

                # Reverse the output so we can get the last revision number
                cmd_svn_log_batch_end_revision_output.reverse()
                batch_end_revision = int(" ".join(cmd_svn_log_batch_end_revision_output).split("revision=\"")[1].split("\"")[0])

            except IndexError as exception:
                logging.warning(f"{repo_key}; IndexError when getting batch start or end revisions for batch size {fetch_batch_size}, skipping this run to retry next run")
                return

                # logging.warning(f"{repo_key}; IndexError when getting batch start or end revisions for batch size {fetch_batch_size}; running the fetch without the batch size limit; exception: {type(exception)}, {exception.args}, {exception}")
                #  <class 'IndexError'>, ('list index out of range',), list index out of range
                # Need to handle the issue where revisions seem to be out of order on the server


        # If we were successful getting both starting and ending revision numbers
        if batch_start_revision and batch_end_revision:

            # Use them
            cmd_git_svn_fetch += ["--revision", f"{batch_start_revision}:{batch_end_revision}"]

    except Exception as exception:

        # Log a warning if this fails, and run the fetch without the --revision arg
        # logging.warning(f"{repo_key}; failed to get batch start or end revision for batch size {fetch_batch_size}; running the fetch without the batch size limit; exception: {type(exception)}, {exception.args}, {exception}")

        logging.warning(f"{repo_key}; failed to get batch start or end revision for batch size {fetch_batch_size}; skipping this run to retry next run; exception: {type(exception)}, {exception.args}, {exception}")
        return

    # Start the fetch
    cmd_git_svn_fetch_string_may_have_batch_range = " ".join(cmd_git_svn_fetch)
    logging.info(f"{repo_key}; fetching with {cmd_git_svn_fetch_string_may_have_batch_range}")
    git_svn_fetch_result = subprocess_run(cmd_git_svn_fetch, password, password)

    # If the fetch succeed, and if we have a batch_end_revision
    if git_svn_fetch_result["returncode"] == 0 and batch_end_revision:

        # Store the ending revision number
        cmd_git_set_batch_end_revision.append(str(batch_end_revision))
        subprocess_run(cmd_git_set_batch_end_revision)

    clean_remote_branches(local_repo_path)

    # Set default branch
    # git symbolic-ref HEAD refs/heads/trunk
    # git symbolic-ref HEAD refs/heads/{git_default_branch}


def clean_remote_branches(local_repo_path):

    # Git svn and git tfs both create converted branches as remote branches, so the Sourcegraph clone doesn't show them to users
    # Need to convert the remote branches to local branches, so Sourcegraph users can see them

    # TODO: Find out how to set the default branch, or if this is already taken care of with the git conifg --global init.defaultBranch setting

    cmd_git_garbage_collection  = ["git", "-C", local_repo_path, "gc"]
    subprocess_run(cmd_git_garbage_collection)

    # Edit .git/packed-refs

    # Find
    #  refs/remotes/origin/tags/
    # Replace with
    #  refs/tags/
    # sed -i.backup 's/\ refs\/remotes\/origin\/tags\//\ refs\/tags\//g' packed-refs

    # Find
    #  refs/remotes/origin/
    # Replace with
    #  refs/heads/
    # sed -i.backup 's/\ refs\/remotes\/origin\//\ refs\/heads\//g' packed-refs


    packed_refs_file_path           = f"{local_repo_path}/.git/packed-refs"
    packed_refs_file_backup_path    = f"{packed_refs_file_path}-backup"

    string_replacements = [
        (" refs/remotes/origin/tags/"   , " refs/tags/"     ),
        (" refs/remotes/origin/"        , " refs/heads/"    )
    ]

    # # The .git/packed-refs file only exists if git gc found stuff to pack into it
    # if os.path.exists(packed_refs_file_path):

    #     # Take a backup, so we can compare before and after
    #     shutil.copy2(packed_refs_file_path, packed_refs_file_backup_path)

    #     with open(packed_refs_file_path, "r") as packed_refs_file:

    #         read_lines = packed_refs_file.readlines()
    #         for read_line in read_lines:
    #             logging.debug(f"Contents of {packed_refs_file_path} before cleanup: {read_line}")

    #     with open(packed_refs_file_path, "r") as packed_refs_file:

    #         packed_refs_file_content = packed_refs_file.read()

    #     with open(packed_refs_file_path, "w") as packed_refs_file:

    #         # Ensure the string replacements are done in the correct order
    #         for string_replacement in string_replacements:

    #             packed_refs_file_content = packed_refs_file_content.replace(string_replacement[0], string_replacement[1])

    #         packed_refs_file.write(packed_refs_file_content)

    #     with open(packed_refs_file_path, "r") as packed_refs_file:

    #         read_lines = packed_refs_file.readlines()
    #         for read_line in read_lines:
    #             logging.debug(f"Contents of {packed_refs_file_path} after cleanup: {read_line}")

    # else:

    #     logging.debug(f"No git packed-refs file to fix branches and tags, at {packed_refs_file_path}")



def redact_password(args, password=None):

    if password == None:

        args_without_password = args

    else:

        if isinstance(args, list):

            # AttributeError: 'list' object has no attribute 'replace'
            # Need to iterate through strings in list
            args_without_password = []
            for arg in args:

                if password in arg:

                    arg = arg.replace(password, "REDACTED-PASSWORD")

                args_without_password.append(arg)

        elif isinstance(args, str):

            if password in arg:
                args_without_password = arg.replace(password, "REDACTED-PASSWORD")

        elif isinstance(args, dict):

            for key in args.keys():

                if password in args[key]:
                    args[key] = args[key].replace(password, "REDACTED-PASSWORD")

            args_without_password = args

        else:

            logging.error(f"redact_password() doesn't handle args of type {type(args)}")
            args_without_password = None

    return args_without_password


def subprocess_run(args, password=None, echo_password=None, quiet=False):

    return_dict                 = {}
    return_dict["returncode"]   = 1
    return_dict["output"]       = None
    subprocess_output_to_log    = None

    try:

        # Create the process object and start it
        subprocess_to_run = psutil.Popen(
            args    = args,
            stdin   = subprocess.PIPE,
            stdout  = subprocess.PIPE,
            stderr  = subprocess.STDOUT,
            text    = True,
        )

        # Get the process attributes from the OS
        process_dict = subprocess_to_run.as_dict()

        # Redact passwords for logging
        process_dict = redact_password(process_dict, password)

        # Log a starting message
        status_message = "started"
        print_process_status(process_dict, status_message)

        # If password is provided to this function, feed it into the subprocess' stdin pipe
        # communicate() also waits for the process to finish
        if echo_password:
            subprocess_output = subprocess_to_run.communicate(password)

        else:
            subprocess_output = subprocess_to_run.communicate()

        # Redact password from output for logging
        subprocess_output = subprocess_output[0].splitlines()
        subprocess_output_to_log = redact_password(subprocess_output, password)

        # Set the output to return
        return_dict["output"] = subprocess_output

        # If the output is longer than max_output_total_characters, it's probably just a list of all files converted, so truncate it
        max_output_total_characters = 1000
        max_output_line_characters  = 100
        max_output_lines            = 10

        if len(str(subprocess_output_to_log)) > max_output_total_characters:

            # If the output list is longer than max_output_lines lines, truncate it
            subprocess_output_to_log = subprocess_output_to_log[-max_output_lines:]
            subprocess_output_to_log.append(f"...LOG OUTPUT TRUNCATED TO {max_output_lines} LINES")

            # Truncate really long lines
            for i in range(len(subprocess_output_to_log)):

                if len(subprocess_output_to_log[i]) > max_output_line_characters:
                    subprocess_output_to_log[i] = textwrap.shorten(subprocess_output_to_log[i], width=max_output_line_characters, placeholder=f"...LOG LINE TRUNCATED TO {max_output_line_characters} CHARACTERS")

        # If the process exited successfully
        if subprocess_to_run.returncode == 0:

            return_dict["returncode"] = 0

            status_message = "succeeded"
            print_process_status(process_dict, status_message, subprocess_output_to_log)

        else:

            status_message = "failed"

            log_level = logging.ERROR

            if quiet:
                log_level = logging.DEBUG

            print_process_status(process_dict, status_message, subprocess_output_to_log, log_level=log_level)

    except subprocess.CalledProcessError as exception:

            status_message = f"raised an exception: {type(exception)}, {exception.args}, {exception}"

            log_level = logging.ERROR

            if quiet:
                log_level = logging.DEBUG

            print_process_status(process_dict, status_message, subprocess_output_to_log, log_level=log_level)

    if subprocess_to_run.returncode != 0:

        # May need to make this more generic Git for all repo conversions
        # Handle the case of abandoned git svn lock files blocking fetch processes
        # We already know that no other git svn fetch processes are running, because we checked for that before spawning this fetch process
        # fatal: Unable to create '/sourcegraph/src-serve-root/svn.apache.org/wsl/zest/.git/svn/refs/remotes/git-svn/index.lock': File exists.  Another git process seems to be running in this repository, e.g. an editor opened by 'git commit'. Please make sure all processes are terminated then try again. If it still fails, a git process may have crashed in this repository earlier: remove the file manually to continue. write-tree: command returned error: 128
        lock_file_error_strings = ["Unable to create", "index.lock", "File exists"]

        # Handle this as a string,
        stderr_without_password_string = " ".join(subprocess_output_to_log)
        lock_file_error_conditions = (lock_file_error_string in stderr_without_password_string for lock_file_error_string in lock_file_error_strings)
        if all(lock_file_error_conditions):

            try:

                # Get the index.lock file path from stderr_without_password_string
                lock_file_path = stderr_without_password_string.split("Unable to create '")[1].split("': File exists.")[0]

                logging.warning(f"Fetch failed to start due to finding a lockfile in repo at {lock_file_path}, but no fetch process running for this repo, deleting the lockfile so it'll try again on the next run")

                # Careful with recursive function call, don't create infinite recursion and fork bomb the container
                subprocess_run(["rm", "-f", lock_file_path])

            except subprocess.CalledProcessError as exception:
                logging.error(f"Failed to rm -f lockfile at {lock_file_path} with exception: {type(exception)}, {exception.args}, {exception}")

            except ValueError as exception:
                logging.error(f"Failed to find git execution path in command args while trying to delete {lock_file_path} with exception: {type(exception)}, {exception.args}, {exception}")

    return return_dict


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

    # The current approach should return the same list of processes as just ps -ef when a Docker container runs this script as the CMD (pid 1)

    # Get the current process ID, should be 1 in Docker
    os_this_pid = os.getpid()

    # Using a set for built-in deduplication
    process_pids_to_wait_for = set()

    # Get a oneshot snapshot of all processes running this instant
    # Loop through for each processes
    for process in psutil.process_iter():

        # The process may finish in the time between .process_iter() and .parents()
        try:

            # Get all upstream parent PIDs of the process
            # Caught a process doesn't exist exception here, could see if it could be handled
            process_parents_pids = [process_parent.pid for process_parent in process.parents()]

            # If this pid is in the parents, then we know its a child / grandchild / great-grandchild / etc. process of this process
            if os_this_pid in process_parents_pids:

                # Add the process' own PID to the set
                process_pids_to_wait_for.add(process.pid)

                # Loop through the process' parents and add them to the set too
                for process_parents_pid in process_parents_pids:

                    process_pids_to_wait_for.add(process_parents_pid)

        except psutil.NoSuchProcess as exception:

            logging.debug(f"Caught an exception when listing parents of processes: {exception}")

    # Remove this script's PID so it's not waiting on itself
    process_pids_to_wait_for.discard(os_this_pid)

    # Now that we have a set of all child / grandchild / etc PIDs without our own
    # Loop through them and wait for each one
    # If the process is a zombie, then waiting for it:
        # Gets the return value
        # Removes the process from the OS' process table
        # Raises an exception
    for process_pid_to_wait_for in process_pids_to_wait_for:

        process_dict = {}
        status_message = ""
        process_to_wait_for = None

        try:

            # Create an instance of a Process object for the PID number
            # Raises psutil.NoSuchProcess if the PID has already finished
            process_to_wait_for = psutil.Process(process_pid_to_wait_for)

            # Get the process attributes from the OS
            process_dict = process_to_wait_for.as_dict()

            # This rarely fires, ex. if cleaning up processes at the beginning of a script execution and the process finished during the interval
            if process_to_wait_for.status() == psutil.STATUS_ZOMBIE:
                status_message = "is a zombie"

            # Wait a short period, and capture the return status
            # Raises psutil.TimeoutExpired if the process is busy executing longer than the wait time
            return_status = process_to_wait_for.wait(0.1)
            status_message = f"finished with return status: {str(return_status)}"

        except psutil.NoSuchProcess as exception:
            status_message = "finished on wait"

        except psutil.TimeoutExpired as exception:
            status_message = "still running"

        except Exception as exception:
            status_message = f"raised an exception while waiting: {type(exception)}, {exception.args}, {exception}"

        if "pid" not in process_dict.keys():
            process_dict["pid"] = process_pid_to_wait_for

        print_process_status(process_dict, status_message)


def print_process_status(process_dict = {}, status_message = "", std_out = "", log_level = logging.DEBUG):

    log_message = ""

    process_attributes_to_log = [
        "cmdline",
        "status",
        "ppid",
        "num_fds",
        "cpu_times",
        "connections_count",
        "connections",
    ]

    try:

        # Formulate the log message
        log_message = f"pid {process_dict['pid']}; {status_message}"

        if status_message != "started" and "create_time" in process_dict.keys():

            process_clock_time_seconds = time.time() - process_dict["create_time"]
            process_clock_time_formatted = time.strftime("%H:%M:%S", time.localtime(process_clock_time_seconds))
            log_message += f"; running for {process_clock_time_formatted}"

        # Pick the interesting bits out of the connections list
        # connections is usually in the dict, as a zero-length list of "pconn"-type objects, (named tuples of tuples)
        if "connections" in process_dict.keys():

            connections = process_dict["connections"]

            if isinstance(connections, list):

                process_dict["connections_count"] = len(process_dict["connections"])

                connections_string = ""

                for connection in connections:

                    # raddr=addr(ip='93.186.135.91', port=80), status='ESTABLISHED'),
                    connections_string += ":".join(map(str,connection.raddr))
                    connections_string += ":"
                    connections_string += connection.status
                    connections_string += ", "

                process_dict["connections"] = connections_string[:-2]

        process_dict_to_log = {key: process_dict[key] for key in process_attributes_to_log if key in process_dict}
        log_message += f"; process_dict {process_dict_to_log}"

        if std_out:
            log_message += f"; std_out {std_out}"

    except psutil.NoSuchProcess as exception:
        log_message = f"pid {process_dict['pid']}; finished on status check"

    # except Exception as exception:
    #     log_level   = logging.ERROR
    #     exception_string = " ".join(traceback.format_exception(exception)).replace("\n", " ")
    #     log_message = f"Exception raised while checking process status. Exception: {exception_string}"

    finally:
        # Log the message
        logging.log(log_level, log_message)


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

        git_config_safe_directory()

        parse_repos_to_convert_file_into_repos_dict()
        clone_svn_repos()
        # clone_tfs_repos()
        # clone_git_repos()

        status_update_and_cleanup_zombie_processes()

        logging.info(f"Finishing {script_name} run {script_run_number} with args: " + str(environment_variables_dict))

        # Sleep the configured interval
        logging.info(f"Sleeping for REPO_CONVERTER_INTERVAL_SECONDS={environment_variables_dict['REPO_CONVERTER_INTERVAL_SECONDS']} seconds")

        script_run_number += 1
        time.sleep(environment_variables_dict["REPO_CONVERTER_INTERVAL_SECONDS"])


if __name__ == "__main__":
    main()
