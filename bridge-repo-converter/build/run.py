#!/usr/bin/env python3
# Python 3.12.1

### TODO:
    # Lock files to prevent parallel execution on the same repo
        # Lock files should already be handled by git svn
        # function check_and_create_lock_file()
        # {
        #     if [ -f $LOCK_FILE ]; then
        #         PID=$(cat $LOCK_FILE)
        #         if ps -p $PID > /dev/null; then
        #             echo "this script is currently running (PID: $PID)"
        #             return 1
        #         else
        #             rm -f $LOCK_FILE
        #         fi
        #     fi
        #     mkdir -p $(dirname $LOCK_FILE)
        #     echo $$ > $LOCK_FILE
        # }
    # Handle author files
    # Check for clone completion, and log it
    # Configure batch size, history start, etc.

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

# Global variables
args_dict = {}
repos_to_convert_dict = {}
svn_repo_clone_queue_list = []
tfvc_repo_clone_queue_list = []
git_repo_clone_queue_list = []

# Fork a process and don't wait for it to finish
def fork_and_forget(*args):

    forked_process = Process(args=args)
    forked_process.start()


# Fork a process and wait for it to finish
def fork_and_wait(*args):

    forked_process = Process(args=args)
    forked_process.start()
    forked_process.join()
    return forked_process.exitcode


def parse_args():

    # Parse the command args
    parser = argparse.ArgumentParser(
        description     = "Clone TFVC and SVN repos, convert them to Git, then serve them via src serve-git",
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
        help    = "/sourcegraph/repos-to-convert.yaml file path, to read a list of TFVC / SVN repos and access tokens to iterate through",
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


def set_logging():

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


def load_repos_to_convert_file_into_dict():

    # Load the repos-to-convert.yaml file
    try:

        # Open the file
        with open(args_dict["repos_to_convert_file"], "r") as repos_to_convert_file:

            # Load the YAML file into a dict
            repos_to_convert_temp_dict = yaml.safe_load(repos_to_convert_file)
            logging.debug(json.dumps(repos_to_convert_temp_dict))

            # Weird thing we have to do to persist the dict in the global variable
            for key in repos_to_convert_temp_dict:
                repos_to_convert_dict[key] = repos_to_convert_temp_dict[key]
            logging.debug(json.dumps(repos_to_convert_dict))


    except FileNotFoundError:

        logging.error(f"repos-to-convert.yaml file not found at {args_dict['repos_to_convert_file']}")
        sys.exit(1)

    except AttributeError:

        logging.error(f"Invalid YAML file format in {args_dict['repos_to_convert_file']}, please check the structure matches the format in the README.md")
        sys.exit(2)


def clean_form_and_validate_svn_repo(svn_repo_string, svn_repo_server_key):

    # Declare variables and set defaults
    svn_repo_code_root = ""
    code_host_name = ""
    converted_git_org_name = ""
    converted_git_repo_name = ""
    converted_git_repo_default_branch  = "main"
    converted_git_repo_ignore_file_path = ".gitignore"
    username = ""
    password = ""

    # Clean + Form

    # Step 3: Check if the user provided the needed config in the yaml file
        # Work the way up the order of precedence, and stop on the first value

    # Step 4: Infer any information needed but not provided

    # Settings we expect to have for an SVN repo:
        # Required from the user
            # svn-repo-code-root
        # Needed but can be inferred from the svn-repo-code-root
            # code-host-name
            # converted-git-org-name
            # converted-git-repo-name
        # Have defaults the user can override
            # converted-git-repo-default-branch: main
            # converted-git-repo-ignore-file-path: .gitignore
        # Optional
            # username
            # password

    # Order of precedence
        # 1. Settings in the list item with the svn-repo-code-root
            # This would be if type(svn_repo_server_key_repos) == dict:
        # 2. Settings in the servers list, with the matching server key
        # 3. Globals
        # 4. Inferred
        # 5. Defaults

    # Start from the bottom and work our way up

    # svn-repo-code-root
    # If they give us an svn+ssh scheme, give them an error it's not supported yet, and skip it
    if svn_repo_string.startswith("svn+ssh://"):
        logging.error(f"svn+ssh:// scheme found in {svn_repo_string}, SVN over SSH is not supported at this time, please use https:// or http:// instead")
        return False

    # If it doesn't start with a valid scheme, then prepend http:// to it
    svn_valid_url_schemes = [
        "http://",
        "https://",
        "svn://"
    ]
    if not any(svn_repo_string.startswith(scheme) for scheme in svn_valid_url_schemes):
        logging.warning(f"SVN repo {svn_repo_string} doesn't start with a URL scheme, assuming http://")
        svn_repo_string = "http://" + svn_repo_string

    svn_repo_code_root = svn_repo_string


    # code-host-name
    # Try to read it from servers.svn.<svn-repo-server-key>.code-host-name
    code_host_name = repos_to_convert_dict.get("servers",{}).get("svn",{}).get(svn_repo_server_key,{}).get("code-host-name","")
    if code_host_name:
        # If that succeeded, great, you're done
        logging.debug(f"Found code-host-name in servers.svn.{svn_repo_server_key}: {code_host_name}")
    else:
        # Otherwise, try to read it from global.svn.code-host-name
        code_host_name = repos_to_convert_dict.get("global",{}).get("svn",{}).get("code-host-name","")
        if code_host_name:
            logging.debug(f"Found code-host-name in global.svn: {code_host_name}")
        else:
            # Otherwise, infer it from the svn-repo-code-root
            code_host_name = svn_repo_code_root.split("//")[1].split("/")[0]
            logging.debug(f"Inferred code-host-name from {svn_repo_code_root}: {code_host_name}")

    # converted-git-org-name

    # logging.debug(repos_to_convert_dict)
    # svn_repo_servers_dict = repos_to_convert_dict.get("repos",{}).get("svn",{})

    # if len(svn_repo_servers_dict) == 0:
    #     logging.debug("No SVN repos found in repos-to-convert.yaml")
    #     return
    svn_repo_object = {
        "svn-repo-code-root" : svn_repo_code_root,
        "code-host-name" : code_host_name,
        "converted-git-org-name" : "",
        "converted-git-repo-name" : "",
        "converted-git-repo-default-branch" : "main",
        "converted-git-repo-ignore-file-path" : ".gitignore",
        "username" : "",
        "password" : ""
    }

    # Validate
    if False:
        svn_repo_object = False

    return svn_repo_object

def load_svn_repo_objects_into_clone_queue_list():

    # Step 1: Get the list of svn-repo-code-root
    # Get everything under the
    # repos:
    #   svn:
    #     server:
    #       repos

    # For each depth to loop through
    # Try and get the dict below the starting key
        # Use an empty default value to avoid a fatal error
        # Debug print it
        # If it's empty, return or continue
    # If it's a type string, it's only one item, not a list, so process the one and don't loop deeper
    # If it's a type dict, then loop through the list and process each item

    logging.debug(repos_to_convert_dict)
    svn_repo_servers_dict = repos_to_convert_dict.get("repos",{}).get("svn",{})

    if len(svn_repo_servers_dict) == 0:
        logging.debug("No SVN repos found in repos-to-convert.yaml")
        return

    # We've made it this far, so repos.svn exists and isn't empty
    # Step 2: Loop through the list
    for svn_repo_server_key in svn_repo_servers_dict.keys():

        # .keys() returns a list of strings
        # svn_repo_server_key should be a string
        # Don't try and use it as a dict
        # Use it as a key to get a list or dict of repos below

        # svn_repo_server_key at this point is the arbitrary name the user picked
        # which we have to match from the repos dict to the servers dict
        logging.debug(f"Found SVN repo server: {svn_repo_server_key}")

        # Could be empty, a string, list of strings, or dict
        svn_repo_server_key_repos = svn_repo_servers_dict[svn_repo_server_key]

        # If it's empty, return
        if len(svn_repo_server_key_repos) == 0:
            logging.debug(f"No SVN repos found for server: {svn_repo_server_key}")
            continue

        # If it's a string, assume it's a svn-repo-code-root
        # Make it a list, so we only have to write the code once
        if type(svn_repo_server_key_repos) == str:

            svn_repo_server_key_repos = [svn_repo_server_key_repos]

        # If it's a list of strings, assume each string is a svn-repo-code-root
        if type(svn_repo_server_key_repos) == list:

            for svn_repo_string in svn_repo_server_key_repos:

                svn_repo_object = clean_form_and_validate_svn_repo(svn_repo_string, svn_repo_server_key)

                if svn_repo_object is not False:

                    # svn_repo_code_root is finally a valid SVN repo code root
                    logging.debug(f"Found SVN repo {svn_repo_string} under server {svn_repo_server_key}")

                    # Add it to the queue
                    svn_repo_clone_queue_list.append(svn_repo_object)

                else:

                    logging.warning(f"Found invalid SVN repo {svn_repo_string} under server {svn_repo_server_key}")

        # If it's a dict, assume it's a list of repos with repo-level configs
        # It might be one of these keyless list / struct / object things
        #   - repo-url: "ssh://git@git.example.com/repo.git"
        #     converted-git-org-name: org
        #     converted-git-repo-name: repo-main
        #     converted-git-default-branch: main
        if type(svn_repo_server_key_repos) == dict:

            for svn_repo in svn_repo_server_key_repos.keys():

                logging.debug(f"Found SVN repo {svn_repo} under server {svn_repo_server_key_repos}")




def clone_svn_repos():

    # Declare an empty dict for SVN repos to extract them from the repos_to_convert_dict
    svn_repos_dict = {}

    # Loop through the repos_to_convert_dict, find the type: SVN repos, then add them to the dict of SVN repos
    for repo_key in repos_to_convert_dict.keys():

        repo_type = repos_to_convert_dict[repo_key].get('type','').lower()

        if repo_type == 'svn':

            svn_clone_command = "git svn clone "
            svn_repo_code_root      = repos_to_convert_dict[repo_key].get('svn-repo-code-root','')
            username                = repos_to_convert_dict[repo_key].get('username','')
            password                = repos_to_convert_dict[repo_key].get('password','')
            code_host_name          = repos_to_convert_dict[repo_key].get('code-host-name','')
            git_org_name            = repos_to_convert_dict[repo_key].get('git-org-name','')
            git_repo_name           = repos_to_convert_dict[repo_key].get('git-repo-name','')
            git_default_branch      = repos_to_convert_dict[repo_key].get('git-default-branch','main')
            authors_file_path       = repos_to_convert_dict[repo_key].get('authors-file-path','')
            git_ignore_file_path    = repos_to_convert_dict[repo_key].get('git-ignore-file-path','')
            layout                  = repos_to_convert_dict[repo_key].get('layout','')
            trunk                   = repos_to_convert_dict[repo_key].get('trunk','')
            tags                    = repos_to_convert_dict[repo_key].get('tags','')
            branches                = repos_to_convert_dict[repo_key].get('branches','')

            # If lockfile exists with svn_repo_code_root and pid number
                # If the pid from the lockfile is still running, with a command arg including git svn
                    # Then skip this run
                # Otherwise, remove the lockfile and continue with the run

            # If default branch was provided, set it, otherwise set main
            fork_and_forget(["git", "config", "--global", "init.defaultBranch", git_default_branch])

            # If username and password were provided, use them to login
            if username and password:
                logging.info(f"Logging in to SVN repo {repo_key} with username {username}")
                result = fork_and_wait(["svn", "info", "--non-interactive", "--username", username, "--password", password, svn_repo_code_root])
                if result == 0:
                    logging.info(f"Logged in successfully to SVN repo {repo_key} with username {username}")
                else:
                    logging.warning(f"Failed to login to SVN repo {repo_key} with username {username}")

            # # If username was provided
            # if username:
            #     svn_clone_command += f" --username={username} "

            # If layout was specified as standard
            if layout == "standard":
                svn_clone_command += " --stdlayout "

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

            fork_and_wait(["git", "-C", repo_path, "svn", "init", svn_repo_code_root])

            # This didn't seem to succeed automatically the first time, but succeeded manually
            # May need to add a delay / wait for the git init to finish
            fork_and_wait(["git", "config", "--file", f"{repo_path}/.git/config", "--bool", "core.bare", "true"])

            if git_ignore_file_path:
                try:
                    logging.info(f"Copying gitignore file from {git_ignore_file_path} to {repo_path}")
                    shutil.copy2(git_ignore_file_path, repo_path)
                except FileNotFoundError:
                    logging.warning(f"Gitignore file not found at {git_ignore_file_path}")

            logging.info(f"Cloning SVN repo {repo_key}")

            # Fork the process
            fork_and_forget(["git", "-C", repo_path, "svn", "fetch"])
            # Create the lockfile with the forked pid number


def clone_tfvc_repos():

    # Declare an empty dict for TFVC repos to extract them from the repos_to_convert_dict
    tfvc_repos_dict = {}

    # Loop through the repos_to_convert_dict, find the type: tfvc repos, then add them to the dict of TFVC repos
    for repo_key in repos_to_convert_dict.keys():

        repo_type = repos_to_convert_dict[repo_key].get('type','').lower()

        if repo_type == 'tfs' or repo_type == 'tfvc':

            tfvc_repos_dict[repo_key] = repos_to_convert_dict[repo_key]


    logging.debug("Cloning TFVC repos" + str(tfvc_repos_dict))


def clone_git_repos():
    pass


def main():

    parse_args()
    set_logging()
    logging.debug(f"{os.path.basename(__file__)} starting with args " + str(args_dict))

    load_repos_to_convert_file_into_dict()
    load_svn_repo_objects_into_clone_queue_list()
    clone_svn_repos()
    clone_tfvc_repos()
    clone_git_repos()


if __name__ == "__main__":
    main()
