#!/usr/bin/env python3
# Python 3.12.1

### TODO:

    # Configure batch size, so we see repos in Sourcegraph update as the fetch jobs progress

        # git svn fetch --revision START:END
        # git svn fetch --revision BASE:[number]
            # to speed things along - so I recently added that as an answer to my own question (update now taking routinely less than an hour).  Still that all seemed really odd. "--revision" isn't documented as an option to "git svn fetch", you need to dig START out of .git/svn/.metadata and END out of the SVN repository.

    # Git SSH clone

    # Parallelism
        # Poll the fetch process
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
import argparse                                             # https://docs.python.org/3/library/argparse.html
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
# import psutil                                               # https://pypi.org/project/psutil/
import yaml                                                 # https://pyyaml.org/wiki/PyYAMLDocumentation


# Global variables
script_name = os.path.basename(__file__)
args_dict = {}
repos_dict = {}
running_processes = []


def signal_handler(signal, frame):
    signal_name = signal.Signals(signal).name
    logging.debug(f"Received signal {signal_name}: {signal} frame: {frame}")
signal.signal(signal.SIGINT, signal_handler)


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

    # Clear the dict for this execution to remove repos which have been removed from the yaml file
    repos_dict.clear()

    # Parse the repos-to-convert.yaml file
    try:

        # Open the file
        with open(args_dict["repos_to_convert_file"], "r") as repos_to_convert_file:

            # This should return a dict
            code_hosts_list_temp = yaml.safe_load(repos_to_convert_file)

            # Weird thing we have to do
            # Reading directory into repos_dict doesn't persist the dict outside the function
            for repo_dict_key in code_hosts_list_temp.keys():

                # Store the repo_dict_key in the repos_dict
                repos_dict[repo_dict_key] = code_hosts_list_temp[repo_dict_key]

            logging.info(f"Parsed {len(repos_dict)} repos from {args_dict['repos_to_convert_file']}")

    except FileNotFoundError:

        logging.error(f"repos-to-convert.yaml file not found at {args_dict['repos_to_convert_file']}")
        sys.exit(1)

    except (AttributeError, yaml.scanner.ScannerError) as e:

        logging.error(f"Invalid YAML file format in {args_dict['repos_to_convert_file']}, please check the structure matches the format in the README.md. Exception: {type(e)}, {e.args}, {e}")
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
        repo_path = str(args_dict["repo_share_path"]+"/"+code_host_name+"/"+git_org_name+"/"+git_repo_name)

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

            completed_ps_command = subprocess.run(ps_command, check=True, capture_output=True, text=True)

            if cmd_run_git_svn_fetch_without_password in completed_ps_command.stdout:

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
            subprocess_run(cmd_run_git_svn_init, password)

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

        process = multiprocessing.Process(target=subprocess_run, name="git svn fetch "+git_repo_name, args=(cmd_run_git_svn_fetch, password, arg_svn_echo_password))
        process.start()
        # process.join() # join prevents zombies, but it also blocks parallel processing
        running_processes.append(process)


def redact_password_from_list(args, password=None):

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

    # Using the subprocess module
    # https://docs.python.org/3/library/subprocess.html#module-subprocess
    # Waits for the process to complete

    # Redact passwords for logging
    # Convert to string because that's all we're using it for anyway
    args_without_password_string = ' '.join(redact_password_from_list(args, password))
    std_out_without_password = None

    try:

        logging.debug(f"Starting subprocess: {args_without_password_string}")

        # If password is provided to this function, feed it into the subprocess' stdin pipe
        # Otherwise the input keyword arg is still set to the None type
        if echo_password:
            finished_process = subprocess.run(args, capture_output=True, check=True, text=True, input=password)
        else:
            finished_process = subprocess.run(args, capture_output=True, check=True, text=True)

        # If the subprocess didn't raise an exception, then it succeeded
        std_out_without_password = ' '.join(redact_password_from_list(finished_process.stdout.splitlines(), password))
        logging.info(f"Subprocess succeeded: {args_without_password_string} with output: {std_out_without_password}")

    except subprocess.CalledProcessError as error:

        std_err_without_password = ' '.join(redact_password_from_list(error.stderr.splitlines(), password))
        logging.error(f"Subprocess failed: {args_without_password_string} with error: {error}, and stderr: {std_err_without_password}")

        # Handle the case of git svn lock files blocking fetch processes
        # We already know that no other git svn fetch processes are running, because we checked for that before spawning this fetch process
        # fatal: Unable to create '/sourcegraph/src-serve-root/svn.apache.org/wsl/zest/.git/svn/refs/remotes/git-svn/index.lock': File exists.  Another git process seems to be running in this repository, e.g. an editor opened by 'git commit'. Please make sure all processes are terminated then try again. If it still fails, a git process may have crashed in this repository earlier: remove the file manually to continue. write-tree: command returned error: 128
        if ".git/svn/refs/remotes/git-svn/index.lock" in std_err_without_password:

            try:

                # Get git -C file path from args
                lock_file_path = args[args.index("-C") + 1] + "/.git/svn/refs/remotes/git-svn/index.lock"

                logging.warning(f"git svn fetch failed to start due to finding a lockfile in repo at {lock_file_path}. Deleting the lockfile so it'll try again on the next run.")
                subprocess_run(["rm", "-f", lock_file_path])

            except subprocess.CalledProcessError as error:
                logging.error(f"Failed to rm -f lockfile at {lock_file_path} with error: {error}")

            except ValueError as error:
                logging.error(f"Failed to find git execution path in command args while trying to delete {lock_file_path} with error: {error}")

    return std_out_without_password


def clone_tfs_repos():

    # Declare an empty dict for TFS repos to extract them from the repos_dict
    tfs_repos_dict = {}

    # Loop through the repos_dict, find the type: tfs repos, then add them to the dict of TFS repos
    for repo_key in repos_dict.keys():

        repo_type = repos_dict[repo_key].get('type','').lower()

        if repo_type == 'tfs' or repo_type == 'tfvc':

            tfs_repos_dict[repo_key] = repos_dict[repo_key]


    logging.info("Cloning TFS repos" + str(tfs_repos_dict))


def status_update_and_cleanup_zombie_processes():

    try:

        for process in running_processes:

            if process.is_alive():
                logging.info(f"pid {process.pid} still running: {process.name}")
            else:
                logging.info(f"Process finished with exit code {process.exitcode}: {process.name}")
                running_processes.remove(process)

    except Exception as e:

        logging.error(f"Failed while checking for zombie processes, Exception: {type(e)}, {e.args}, {e}")

    logging.debug("Cleaning up zombie processes")

    # Returns a list of all child processes still running
    # Also joins all completed (zombie) processes to clear them
    multiprocessing.active_children()


def main():

    # Run every 60 minutes by default
    run_interval_seconds = os.environ.get('BRIDGE_REPO_CONVERTER_INTERVAL_SECONDS', 3600)
    run_number = 0

    parse_args()
    set_logging()

    cmd_cfg_git_safe_directory = ["git", "config", "--system", "--add", "safe.directory", "\"*\""]
    subprocess_run(cmd_cfg_git_safe_directory)

    logging.debug("Multiprocessing module using start method: " + multiprocessing.get_start_method())

    while True:

        logging.info(f"Starting {script_name} run {run_number} with args: " + str(args_dict))

        status_update_and_cleanup_zombie_processes()

        parse_repos_to_convert_file_into_repos_dict()
        clone_svn_repos()
        # clone_tfs_repos()

        logging.info(f"Finishing {script_name} run {run_number} with args: " + str(args_dict))
        run_number += 1

        status_update_and_cleanup_zombie_processes()
        # Sleep the configured interval
        # Wait 1 second for the last repo sub process to get kicked off before logging this message, otherwise it gets logg out of order
        time.sleep(1)
        logging.info(f"Sleeping for BRIDGE_REPO_CONVERTER_INTERVAL_SECONDS={run_interval_seconds} seconds")
        time.sleep(int(run_interval_seconds))


if __name__ == "__main__":
    main()
