# Repo Converter

## Experimental - This is not a supported Sourcegraph product
This repo was created for Sourcegraph Implementation Engineering deployments and Managed Services, and is not intended, designed, built, or supported for use in any other scenario. Feel free to open issues or PRs, but responses are best effort.

## Why
Provides a framework to convert non-Git repos into Git format, and in combination with src serve-git, and optionally the Sourcegraph Cloud Private Connect Agent (for Sourcegraph Cloud customers), provide a code host endpoint for the customer's Sourcegraph instance to clone the repos from.

## Setup
1. Clone this repo to a VM with network connectivity to the customer's code hosts
2. Install Docker and Docker's Compose plugin
3. Copy the `./config/example-repos-to-convert.yaml` file to `./config/repos-to-convert.yaml`
4. Modify the contents of the `./config/repos-to-convert.yaml` file:
    - Refer to the contents of the `input_value_types_dict` [here](https://sourcegraph.com/search?q=repo:%5Egithub%5C.com/sourcegraph/implementation-bridges$+input_value_types_dict) for the config parameters available, and the required value types
    - Note that if your code host requires credentials, the current version of this requires the credentials to be stored in this file; it could be modified to read credentials via environment variables, so they could be loaded from a customer's secrets management system at container start time
    - Use extra caution when pasting the YAML files in Windows, as it may use Windows' line endings or extra spaces, which breaks YAML, as a whitespace-dependent format
5. You / we may need to write a new `docker-compose.yaml` file if you need to expose the src serve-git port outside the host / Docker network, without using the Cloud Private Connect Agent
    - There are docker-compose.yaml and override files in a few different directories in this repo, separated by use case, so that each use case only needs to run `docker compose up -d` in one directory, and not fuss around with `-f` paths.
    - The only difference between the docker-compose-override.yaml files in host-ubuntu vs host-wsl is the src-serve-git container's name, which is how we get a separate `dnsName` for each.
    - The `LOG_LEVEL` environment variable should be left undefined to use the default `INFO` in most cases; `DEBUG` is mostly just for visibility on subprocesses getting forked and cleaned up
6. Run `docker compose up -d`
7. Add a Code Host config to the customer's Cloud instance
    - Type: src serve-git
    - `"url": "http://src-serve-git-ubuntu.local:443",`
    - matching the src serve-git container's Docker container name and listening port number from the `docker-compose.yaml`
8. The repo-converter will output the converted repos in the `src-serve-root` directory, where src serve-git will serve them from
