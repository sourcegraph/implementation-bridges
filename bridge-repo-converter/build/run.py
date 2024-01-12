#!/usr/bin/env python3
# Python 3.12.1

### TODO:
    # Author files
    # Atlassian's Java binary to tidy up branches and tags
    # Configure batch size
    # Check for clone completion, and log it
    # Configure history start, etc.

### Notes
# See this migration guide https://www.atlassian.com/git/tutorials/migrating-convert
    # Especially the Clean the new Git repository, to convert branches and tags
    # git config svn.authorsfile


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


def parse_args(args_dict):

    # Parse the command args
    parser = argparse.ArgumentParser(
        description     = "Clone TFS and SVN repos, convert them to Git, then serve them via src serve-git",
        usage           = str("Use " + os.path.basename(__file__) + " --help for more information"),
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-d",
        action  = "store_true",
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
        default = "INFO",
        help    = "Log level",
    )
    parser.add_argument(
        "--quiet", "-q",
        action  = "store_true",
        default = False,
        help    = "Run without logging to stdout",
    )
    parser.add_argument(
        "--repo-path",
        default = "/repos-to-serve",
        help    = "Root of path to directory to store cloned Git repos",
    )
    parsed = parser.parse_args()

    # Store the parsed args in the args dictionary
    args_dict["repos_to_convert_file"]  = Path(parsed.repos_to_convert)
    args_dict["log_file"]               = Path(parsed.log_file)
    args_dict["log_level"]              = parsed.log_level
    args_dict["quiet"]                  = parsed.quiet
    args_dict["repo_path"]              = parsed.repo_path

    if "d" in parsed:
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

    # Declare an empty dict for SVN repos to extract them from the repos_dict
    svn_repos_dict = {}

    # Loop through the repos_dict, find the type: SVN repos, then add them to the dict of SVN repos
    for repo_key in repos_dict.keys():

        repo_type = repos_dict[repo_key].get('type','').lower()

        if repo_type == 'svn':

            svn_clone_command = ["git","svn","clone"]
            svn_repo_code_root      = repos_dict[repo_key].get('svn-repo-code-root','')
            username                = repos_dict[repo_key].get('username','')
            password                = repos_dict[repo_key].get('password','')
            code_host_name          = repos_dict[repo_key].get('code-host-name','')
            git_org_name            = repos_dict[repo_key].get('git-org-name','')
            git_repo_name           = repos_dict[repo_key].get('git-repo-name','')
            git_default_branch      = repos_dict[repo_key].get('git-default-branch','main')
            authors_file_path       = repos_dict[repo_key].get('authors-file-path','')
            git_ignore_file_path    = repos_dict[repo_key].get('git-ignore-file-path','')
            layout                  = repos_dict[repo_key].get('layout','')
            trunk                   = repos_dict[repo_key].get('trunk','')
            tags                    = repos_dict[repo_key].get('tags','')
            branches                = repos_dict[repo_key].get('branches','')

            # Username and password may be required fields, test them by logging in
            if username and password:

                logging.info(f"Logging in to SVN repo {repo_key} with username {username}")
                result = subprocess.run(["svn", "info", "--non-interactive", "--username", username, "--password", password, svn_repo_code_root])

                if result == 0:

                    logging.info(f"Logged in successfully to SVN repo {repo_key} with username {username}")

                else:

                    logging.warning(f"Failed to login to SVN repo {repo_key} with username {username}, skipping this repo")
                    continue

            # If username was provided
            if username:
                svn_clone_command.append(["--username", username])

            # Need to find a way to handle the password and prevent interactive login
            # # If password was provided
            # if password:
            #     svn_clone_command.append(["--password", password])

            # If layout was specified as standard
            if layout == "standard":
                svn_clone_command.append(["--stdlayout"])

            # Otherwise, specify layout
            else:
                if trunk:
                    svn_clone_command += f" --trunk={trunk} "
                if tags:
                    svn_clone_command += f" --tags={tags} "
                for branch in branches:
                    svn_clone_command += f" --branches={branch} "

            # If authors file was provided
            if authors_file_path :
                if os.path.exists(authors_file_path):
                    svn_clone_command += f" --authors-file={authors_file_path} "
                else:
                    logging.warning(f"Authors file not found at {authors_file_path}, skipping")

            # Add final parameters to the clone command
            svn_clone_command += f" {svn_repo_code_root} "
            svn_clone_command += f" {git_repo_name} "

            # Create the directories if they don't already exist
            repo_path = str(args_dict["repo_path"]+"/"+code_host_name+"/"+git_org_name+"/"+git_repo_name)

            # Check if specified path exists
            if not os.path.exists(repo_path):

                # If not, then create it
                os.makedirs(repo_path)

            # If default branch was provided, set it, otherwise set main
            subprocess.run(["git", "config", "--global", "init.defaultBranch", git_default_branch])

            #fork_and_wait(["git", "-C", repo_path, "svn", "init", svn_repo_code_root])
            try:
                subprocess.run(["git", "-C", repo_path, "svn", "init", svn_repo_code_root], check=True)
            except subprocess.CalledProcessError:
                pass

            # Configure the bare clone
            subprocess.run(["git", "config", "--file", f"{repo_path}/.git/config", "--bool", "core.bare", "true"], check=True)

            if git_ignore_file_path:
                try:
                    logging.info(f"Copying gitignore file from {git_ignore_file_path} to {repo_path}")
                    #shutil.copy2(git_ignore_file_path, repo_path)
                except FileNotFoundError:
                    logging.warning(f"Gitignore file not found at {git_ignore_file_path}")

            logging.info(f"Cloning SVN repo {repo_key}")

            # Fork the process

            subprocess.run(["git", "-C", repo_path, "svn", "fetch"], check=True)
            #fork_and_forget(["git", "-C", repo_path, "svn", "fetch"])
            # Create the lockfile with the forked pid number


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
