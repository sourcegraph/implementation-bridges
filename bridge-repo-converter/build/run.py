#!/usr/bin/env python3
# Python 3.12.1

### TODO:
    # Parallelism
        # Current state:
            # The cron job won't start the script if it's currently running
            # The script waits for each fetch job to complete before starting the next one
        # Desired state:
            # Cron job starts the script at every [interval]
            # Script checks the config file to see which repos are in scope
            # Script checks each repo if it already has fetch job running
                # Lock file with command and pid number?
                # If the file exists, but the command and pid number in the file don't match a running process, info that the pid finished without cleaning up the lock file, and delete the lock file
            # If not, script starts a new fetch job
                # Creates a lock file
    # Atlassian's Java binary to tidy up branches and tags
    # Configure batch size
    # Test layout tags and branches as lists / arrays
    # Output status update on clone jobs
        # Revision x of y completed, time taken, ETA for remaining revisions
    # Check for clone completion, and log it
    # Git check if the repo already exists

### Notes
# See this migration guide https://www.atlassian.com/git/tutorials/migrating-convert
    # Especially the Clean the new Git repository, to convert branches and tags
    # Java script repo
    # https://marc-dev.sourcegraphcloud.com/bitbucket.org/atlassian/svn-migration-scripts/-/blob/src/main/scala/Authors.scala

    # authors file
        # java -jar /sourcegraph/svn-migration-scripts.jar authors https://svn.apache.org/repos/asf/eagle > authors.txt
        # Kinda useful, surprisingly fast
        # git config svn.authorsfile # https://git-scm.com/docs/git-svn#Documentation/git-svn.txt---authors-fileltfilenamegt
        # git config svn.authorsProg # https://git-scm.com/docs/git-svn#Documentation/git-svn.txt---authors-progltfilenamegt

    # git gc

    # git default branch for a bare repo git symbolic-ref HEAD refs/heads/trunk

    # git list all config git -C $repo_path config --list

    # clean-git
        # java -Dfile.encoding=utf-8 -jar /sourcegraph/svn-migration-scripts.jar clean-git
        # Initial output looked good
        # Required a working copy
        # Didn't work
        # Corrupted repo

    # Find a python library for manipulating git repos
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
import yaml                                                 # https://pyyaml.org/wiki/PyYAMLDocumentation

# Fork a process and don't wait for it to finish
def fork_and_forget(args):

    forked_process = Process(args=args)
    forked_process.start()


# Fork a process and wait for it to finish
def fork_and_wait(args):

    forked_process = Process(args=args)
    forked_process.start()
    forked_process.join()
    return forked_process.exitcode


def subprocess_run(args, password=False):

    # Copy args to redact passwords for logging
    args_without_password = args.copy()

    if password:
        args_without_password[args_without_password.index(password)] = "REDACTED"

    try:

        logging.debug(f"Starting subprocess: {' '.join(args_without_password)}")
        result = subprocess.run(args, check=True, capture_output=True, text=True)

        if result.returncode == 0:
            logging.debug(f"Subprocess succeeded: {' '.join(args_without_password)} with output: {result.stdout}")

    except subprocess.CalledProcessError as error:

        logging.error(f"Subprocess failed: {' '.join(args_without_password)} with error: {error}")
        result = False

    return result


def parse_args(args_dict):

    # Parse the command args
    parser = argparse.ArgumentParser(
        description     = "Clone TFS and SVN repos, convert them to Git, then serve them via src serve-git",
        usage           = str("Use " + os.path.basename(__file__) + " --help for more information"),
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
        default = str("./" + os.path.basename(__file__) + ".log"),
        help    = "Log file path",
    )
    parser.add_argument(
        "--log-level",
        choices =["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help    = "Log level",
    )
    parser.add_argument(
        "--quiet", "-q",
        action  = "store_true",
        default = False,
        help    = "Run without logging to stdout",
    )
    parser.add_argument(
        "--repo-share-path",
        default = "/repos-to-serve",
        help    = "Root of path to directory to store cloned Git repos",
    )
    parsed = parser.parse_args()

    # Store the parsed args in the args dictionary
    args_dict["repos_to_convert_file"]  = Path(parsed.repos_to_convert)
    args_dict["log_file"]               = Path(parsed.log_file)
    args_dict["quiet"]                  = parsed.quiet
    args_dict["repo_share_path"]        = parsed.repo_share_path

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


def set_logging(args_dict):

    script_name = os.path.basename(__file__)

    # If the user provided the --quiet arg, then only log to file
    if args_dict["quiet"]:

        logging.basicConfig(
            filename    = args_dict["log_file"],
            datefmt     = "%Y-%m-%d %H:%M:%S",
            encoding    = "utf-8",
            format      = f"%(asctime)s; {script_name}; %(levelname)s; %(message)s",
            level       = args_dict["log_level"]
        )

    # Otherwise log to both the file and stdout
    # I haven't found a more elegant way to append the filename / handlers to the logger config, so duplicating the whole basicConfig() call it is
    else:

        logging_handlers = logging.StreamHandler(sys.stdout), logging.FileHandler(args_dict["log_file"])

        logging.basicConfig(
            handlers    = logging_handlers,
            datefmt     = "%Y-%m-%d %H:%M:%S",
            encoding    = "utf-8",
            format      = f"%(asctime)s; {script_name}; %(levelname)s; %(message)s",
            level       = args_dict["log_level"]
        )


def parse_repos_to_convert_file_into_repos_dict(args_dict, repos_dict):

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

    except AttributeError:

        logging.error(f"Invalid YAML file format in {args_dict['repos_to_convert_file']}, please check the structure matches the format in the README.md")
        sys.exit(2)


def clone_svn_repos(args_dict, repos_dict):

    # Loop through the repos_dict, find the type: SVN repos, then add them to the dict of SVN repos
    for repo_key in repos_dict.keys():

        repo_type = repos_dict[repo_key].get('type','').lower()

        if repo_type == 'svn':

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
            layout                  = repos_dict[repo_key].get('layout','').lower()
            trunk                   = repos_dict[repo_key].get('trunk','')
            tags                    = repos_dict[repo_key].get('tags','')
            branches                = repos_dict[repo_key].get('branches','')

            ## Parse config parameters into command args
            # TODO: Interpret code_host_name, git_org_name, and git_repo_name if not given
            repo_path = str(args_dict["repo_share_path"]+"/"+code_host_name+"/"+git_org_name+"/"+git_repo_name)

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
            # Create the repo path if it doesn't exist
            if not os.path.exists(repo_path):
                os.makedirs(repo_path)

            # Log in to the SVN server to test if credentials are needed / provided / valid
            subprocess_run(cmd_svn_run_login, password)

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

            # Fork off the svn_fetch_command
            logging.info(f"Fetch SVN repo {repo_key}")
            git_svn_fetch(cmd_git_run_svn_fetch, password)

            # Create the lockfile with the forked pid number


def git_svn_fetch(cmd_git_run_svn_fetch, password):

    fetch_process = Process(target=subprocess_run, args=(cmd_git_run_svn_fetch, password))
    fetch_process.start()


def clone_tfs_repos(args_dict, repos_dict):

    # Declare an empty dict for TFS repos to extract them from the repos_dict
    tfs_repos_dict = {}

    # Loop through the repos_dict, find the type: tfs repos, then add them to the dict of TFS repos
    for repo_key in repos_dict.keys():

        repo_type = repos_dict[repo_key].get('type','').lower()

        if repo_type == 'tfs' or repo_type == 'tfvc':

            tfs_repos_dict[repo_key] = repos_dict[repo_key]


    logging.debug("Cloning TFS repos" + str(tfs_repos_dict))


def main():

    args_dict = {}
    parse_args(args_dict)
    set_logging(args_dict)
    logging.debug(f"{os.path.basename(__file__)} starting with args " + str(args_dict))

    repos_dict = {}
    parse_repos_to_convert_file_into_repos_dict(args_dict, repos_dict)
    clone_svn_repos(args_dict, repos_dict)
    # clone_tfs_repos(args_dict, repos_dict)



if __name__ == "__main__":
    main()
