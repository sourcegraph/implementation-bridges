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
            # Sort out how to see all branches in Sourcegraph
            # Atlassian's Java binary to tidy up branches and tags?

        # Parallelism
            # Fork processes earlier, so more of the slow serial stuff for each repo happens in its own thread
            # ex. git svn log

        #.gitignore files
            # git svn create-ignore
            # git svn show-ignore
            # https://git-scm.com/docs/git-svn#Documentation/git-svn.txt-emcreate-ignoreem

        # Test layout tags and branches as lists / arrays

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
import json                                                 # https://docs.python.org/3/library/json.html
import logging                                              # https://docs.python.org/3/library/logging.html
import multiprocessing                                      # https://docs.python.org/3/library/multiprocessing.html
import os                                                   # https://docs.python.org/3/library/os.html
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


def git_config_safe_directory():

    cmd_cfg_git_safe_directory = ["git", "config", "--system", "--replace-all", "safe.directory", "\"*\""]
    subprocess_run(cmd_cfg_git_safe_directory)


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

    except (AttributeError, yaml.scanner.ScannerError) as exception:

        logging.error(f"Invalid YAML file format in {environment_variables_dict['REPOS_TO_CONVERT']}, please check the structure matches the format in the README.md. Exception: {type(exception)}, {exception.args}, {exception}")
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
        arg_svn_non_interactive = [ "--non-interactive"     ] # Do not prompt, just fail if the command doesn't work, only used for direct `svn` command
        arg_svn_username        = [ "--username", username  ]
        arg_svn_password        = [ "--password", password  ] # Only used for direct `svn` commands
        arg_svn_echo_password   = None
        arg_svn_repo_code_root  = [ svn_repo_code_root      ]
        arg_git                 = [ "git", "-C", repo_path  ]
        arg_git_cfg             = arg_git + [ "config"      ]
        arg_git_svn             = arg_git + [ "svn"         ]
        arg_batch_end_revision  = [ f"{git_config_namespace}.batch-end-revision" ]

        ## Define commands
        cmd_run_svn_info            = [ "svn", "info"           ] + arg_svn_repo_code_root + arg_svn_non_interactive
        cmd_run_svn_log             = [ "svn", "log", "--xml", "--with-no-revprops" ] + arg_svn_repo_code_root + arg_svn_non_interactive
        cmd_cfg_git_default_branch  = arg_git_cfg + [ "--global", "init.defaultBranch", git_default_branch ] # Possibility of collisions if multiple of these are run overlapping, make sure it's quick between reading and using this
        cmd_run_git_svn_init        = arg_git_svn + [ "init"                                ] + arg_svn_repo_code_root
        cmd_cfg_git_bare_clone      = arg_git_cfg + [ "core.bare", "true"                   ]
        cmd_cfg_git_authors_file    = arg_git_cfg + [ "svn.authorsfile", authors_file_path  ]
        cmd_cfg_git_authors_prog    = arg_git_cfg + [ "svn.authorsProg", authors_prog_path  ]
        cmd_run_git_svn_fetch       = arg_git_svn + [ "fetch"                               ]
        cmd_cfg_git_get_batch_end_revision  = arg_git_cfg + [ "--get" ] + arg_batch_end_revision
        cmd_cfg_git_set_batch_end_revision  = arg_git_cfg               + arg_batch_end_revision
        cmd_cfg_git_get_svn_url             = arg_git_cfg + [ "--get", "svn-remote.svn.url" ]

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
        cmd_run_git_svn_fetch_string = ' '.join(cmd_run_git_svn_fetch)

        try:

            ps_command = ["ps", "-e", "--format", "%a"]

            running_processes = subprocess_run(ps_command)

            running_processes_string = " ".join(running_processes)

            if cmd_run_git_svn_fetch_string in running_processes_string:

                logging.info(f"{repo_key}; Fetching process already running")
                continue

        except Exception as exception:
            logging.warning(f"{repo_key}; Failed to check if fetching process is already running, will try to start it. Exception: {type(exception)}, {exception.args}, {exception}")

        ## Check if we're in the Update state
        # Check if the git repo already exists and has the correct settings in the config file
        try:

            svn_remote_url = subprocess_run(cmd_cfg_git_get_svn_url)[0]

            if svn_remote_url in svn_repo_code_root:

                repo_state = "update"

        except Exception as exception:
            logging.warning(f"{repo_key}; failed to check git config --get svn-remote.svn.url. Exception: {type(exception)}, {exception.args}, {exception}")


        ## Run commands
        # Run the svn info command to test logging in to the SVN server, for network connectivity and credentials
        # Capture the output so we know the max revision in this repo's history
        svn_info = subprocess_run(cmd_run_svn_info, password, arg_svn_echo_password)
        svn_info_string = " ".join(svn_info)

        # Get last changed revision for this repo
        last_changed_rev_string = "Last Changed Rev: "
        if last_changed_rev_string in svn_info_string:
            last_changed_rev = svn_info_string.split(last_changed_rev_string)[1].split(" ")[0]

        # Check if the previous batch end revision is the same as the last changed rev from svn info
        # If yes, we're up to date, continue to the next repo, instead of forking the git svn process to do the same check
        if repo_state == "update":

            #  TypeError: 'NoneType' object is not subscriptable
            try:
                previous_batch_end_revision = subprocess_run(cmd_cfg_git_get_batch_end_revision)[0]
            except Exception as exception:
                previous_batch_end_revision = ""

            if previous_batch_end_revision == last_changed_rev:

                logging.info(f"{repo_key}; local rev {previous_batch_end_revision}, remote rev {last_changed_rev}, local clone is up to date, skipping it")
                continue

            else:

                cmd_run_svn_log_remaining_revs = cmd_run_svn_log + ["--revision", f"{previous_batch_end_revision}:HEAD"]
                svn_log_remaining_revs = subprocess_run(cmd_run_svn_log_remaining_revs, password, arg_svn_echo_password)
                svn_log_remaining_revs_string = " ".join(svn_log_remaining_revs)
                remaining_revs = svn_log_remaining_revs_string.count("revision=")

                logging.info(f"{repo_key}; local rev {previous_batch_end_revision}, remote rev {last_changed_rev}, {remaining_revs} revs remaining to catch up, fetching next batch of commits")


        if repo_state == "create":

            logging.info(f"{repo_key}; didn't find a local clone, creating one")

            # Create the repo path if it doesn't exist
            if not os.path.exists(repo_path):
                os.makedirs(repo_path)

            # Set the default branch before init
            subprocess_run(cmd_cfg_git_default_branch)

            if layout:
                cmd_run_git_svn_init   += ["--stdlayout"]

                # Warn the user if they provided an invalid value for the layout, only standard is supported
                if "standard" not in layout and "std" not in layout:
                    logging.warning(f"{repo_key}; Layout shortcut provided with incorrect value {layout}, only standard is supported for the shortcut, continuing assuming standard, otherwise provide --trunk, --tags, and --branches")

            if trunk:
                cmd_run_git_svn_init   += ["--trunk", trunk]
            if tags:
                cmd_run_git_svn_init   += ["--tags", tags]
            if branches:
                cmd_run_git_svn_init   += ["--branches", branches]

            # Initialize the repo
            subprocess_run(cmd_run_git_svn_init, password, arg_svn_echo_password)

            # Configure the bare clone
            # Testing without the bare clone to see if branching works easier
            # and because I forget why a bare clone was needed
            # subprocess_run(cmd_cfg_git_bare_clone)


        ## Back to steps we do for both Create and Update states, so users can update the below parameters without having to restart the clone from scratch
        # TODO: Check if these configs are already set the same before trying to set them

        # Configure the authors file, if provided
        if authors_file_path:
            if os.path.exists(authors_file_path):
                subprocess_run(cmd_cfg_git_authors_file)
            else:
                logging.warning(f"{repo_key}; authors file not found at {authors_file_path}, skipping configuring it")

        # Configure the authors program, if provided
        if authors_prog_path:
            if os.path.exists(authors_prog_path):
                subprocess_run(cmd_cfg_git_authors_prog)
            else:
                logging.warning(f"{repo_key}; authors prog not found at {authors_prog_path}, skipping configuring it")

        # Configure the .gitignore file, if provided
        if git_ignore_file_path:
            if os.path.exists(git_ignore_file_path):
                shutil.copy2(git_ignore_file_path, repo_path)
            else:
                logging.warning(f"{repo_key}; .gitignore file not found at {git_ignore_file_path}, skipping configuring it")

        # If the user has configured a batch size
        if fetch_batch_size:

            try:

                batch_start_revision    = None
                batch_end_revision      = None

                # Get the revision number to start with
                if repo_state == "update":

                    # Try to retrieve repo-converter.batch-end-revision from git config
                    # previous_batch_end_revision = git config --get repo-converter.batch-end-revision
                    # Need to fail gracefully
                    previous_batch_end_revision = subprocess_run(cmd_cfg_git_get_batch_end_revision)

                    if previous_batch_end_revision:

                        batch_start_revision = int(" ".join(previous_batch_end_revision)) + 1

                if repo_state == "create" or batch_start_revision == None:

                    # If this is a new repo, get the first changed revision number for this repo from the svn server log
                    cmd_run_svn_log_batch_start_revision = cmd_run_svn_log + ["--limit", "1", "--revision", "1:HEAD"]
                    svn_log_batch_start_revision = subprocess_run(cmd_run_svn_log_batch_start_revision, password, arg_svn_echo_password)
                    batch_start_revision = int(" ".join(svn_log_batch_start_revision).split("revision=\"")[1].split("\"")[0])

                if batch_start_revision:

                    # Get the batch size'th revision number for the rev to end this batch range
                    cmd_run_svn_log_batch_end_revision = cmd_run_svn_log + ["--limit", str(fetch_batch_size), "--revision", f"{batch_start_revision}:HEAD"]
                    cmd_run_svn_log_batch_end_revision_output = subprocess_run(cmd_run_svn_log_batch_end_revision, password, arg_svn_echo_password)

                    try:

                        # While we're at it, update the batch starting rev to the first real rev number after the previous end rev +1
                        batch_start_revision = int(" ".join(cmd_run_svn_log_batch_end_revision_output).split("revision=\"")[1].split("\"")[0])

                        # Reverse the output so we can get the last revision number
                        cmd_run_svn_log_batch_end_revision_output.reverse()
                        batch_end_revision = int(" ".join(cmd_run_svn_log_batch_end_revision_output).split("revision=\"")[1].split("\"")[0])

                    except IndexError as exception:
                        logging.warning(f"{repo_key}; IndexError when getting batch start or end revisions for batch size {fetch_batch_size}; running the fetch without the batch size limit; exception: {type(exception)}, {exception.args}, {exception}")


                if batch_start_revision and batch_end_revision:

                    # If we were successful getting both starting and ending revision numbers, then use them
                    cmd_run_git_svn_fetch += ["--revision", f"{batch_start_revision}:{batch_end_revision}"]

                    # Store the ending revision number, hoping that this batch completes successfully, as these revs won't be retried
                    cmd_cfg_git_set_batch_end_revision.append(str(batch_end_revision))
                    subprocess_run(cmd_cfg_git_set_batch_end_revision)

            except Exception as exception:

                # Log a warning if this fails, and run the fetch without the --revision arg
                logging.warning(f"{repo_key}; failed to get batch start or end revision for batch size {fetch_batch_size}; running the fetch without the batch size limit; exception: {type(exception)}, {exception.args}, {exception}")

        # Start the fetch
        cmd_run_git_svn_fetch_string_may_have_batch_range = ' '.join(cmd_run_git_svn_fetch)
        logging.info(f"{repo_key}; fetching with {cmd_run_git_svn_fetch_string_may_have_batch_range}")
        multiprocessing.Process(target=subprocess_run, name=f"subprocess_run({cmd_run_git_svn_fetch})", args=(cmd_run_git_svn_fetch, password, password)).start()


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


def subprocess_run(args, password=None, echo_password=None):

    subprocess_output_to_log    = None
    subprocess_stdout_to_return = None
    subprocess_stderr_to_check  = None

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
        subprocess_output_to_log = redact_password(subprocess_output[0].splitlines(), password)
        subprocess_output_to_log_backup = subprocess_output_to_log.copy()

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

            # Assign the function return value, so the function doesn't return None
            # Create a separate list for the stdout content, so we can log a truncated version, without changing the content for the return value
            subprocess_stdout_to_return = subprocess_output_to_log_backup.copy()

            status_message = "succeeded"
            print_process_status(process_dict, status_message, subprocess_output_to_log)

        else:

            subprocess_stderr_to_check = subprocess_output_to_log

            status_message = "failed"
            print_process_status(process_dict, status_message, subprocess_stderr_to_check, log_level = logging.ERROR)

    except subprocess.CalledProcessError as exception:

            status_message = f"raised an exception: {type(exception)}, {exception.args}, {exception}"
            print_process_status(process_dict, status_message, subprocess_output_to_log, log_level = logging.ERROR)


    if subprocess_stderr_to_check:

        # May need to make this more generic Git for all repo conversions
        # Handle the case of abandoned git svn lock files blocking fetch processes
        # We already know that no other git svn fetch processes are running, because we checked for that before spawning this fetch process
        # fatal: Unable to create '/sourcegraph/src-serve-root/svn.apache.org/wsl/zest/.git/svn/refs/remotes/git-svn/index.lock': File exists.  Another git process seems to be running in this repository, e.g. an editor opened by 'git commit'. Please make sure all processes are terminated then try again. If it still fails, a git process may have crashed in this repository earlier: remove the file manually to continue. write-tree: command returned error: 128
        lock_file_error_strings = ["Unable to create", "index.lock", "File exists"]

        # Handle this as a string,
        stderr_without_password_string = " ".join(subprocess_stderr_to_check)
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

    return subprocess_stdout_to_return


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

        status_message = ""
        process_to_wait_for = None

        try:

            # Create an instance of a Process object for the PID number
            # Raises psutil.NoSuchProcess if the PID has already finished
            process_to_wait_for = psutil.Process(process_pid_to_wait_for)

            # This rarely fires, ex. if cleaning up processes at the beginning of a script execution and the process finished during the interval
            if process_to_wait_for.status() == psutil.STATUS_ZOMBIE:
                status_message = "is a zombie"

            # Get the process attributes from the OS
            process_dict = process_to_wait_for.as_dict()

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

        finally:

            print_process_status(process_dict, status_message)


def print_process_status(process_dict = {}, status_message = "", std_out = "", log_level = logging.DEBUG):

    log_message = ""

    process_attributes_to_log = [
        'status',
        'cmdline',
        'ppid',
        'connections',
        'cpu_times',
        'num_fds',
    ]

    try:

        process_dict_to_log = {key: process_dict[key] for key in process_attributes_to_log if key in process_dict}

        # Calculate the running clock time
        process_clock_time_seconds = time.time() - process_dict['create_time']
        process_clock_time_formatted = time.strftime("%H:%M:%S", time.localtime(process_clock_time_seconds))

        # Formulate the log message
        log_message = f"pid {process_dict['pid']}; {status_message}"

        if status_message != "started":
            log_message += f"; clock time {process_clock_time_formatted}"

        if std_out:
            log_message += f"; std_out {std_out}"

        log_message += f"; process_dict {process_dict_to_log}"

    except psutil.NoSuchProcess as exception:
        log_message = f"pid {process_dict['pid']}; finished on status check"

    except Exception as exception:
        log_level   = logging.ERROR
        exception_string = " ".join(traceback.format_exception(exception)).replace("\n", " ")
        log_message = f"Exception raised while checking process status. Exception: {exception_string}"

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
        time.sleep(environment_variables_dict['REPO_CONVERTER_INTERVAL_SECONDS'])


if __name__ == "__main__":
    main()
