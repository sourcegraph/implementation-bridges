# Run the Sourcegraph Cloud Private Connect Agent and src serve-git together in a Docker Compose file

## Experimental - This is not a supported Sourcegraph product
This repo was created for Sourcegraph Implementation Engineering deployments, and is not intended, designed, built, or supported for use in any other scenario. Feel free to open issues or PRs, but responses are best effort.

## Why
Running src serve-git and the agent together on the same Docker network allows the agent to use Docker's DNS to reach src serve-git, and prevents src serve-git's unauthenticated HTTP endpoint from needing to be opened outside of the Docker host.

Docker compose also allows for easier upgrades, troubleshooting, monitoring, logging, flexibility of hosting, etc. than running the binaries directly on the OS.

## Setup - Sourcegraph Staff Only
1. Add the needed entries to the sourcegraphConnect targetGroups list in the Cloud instance's config.yaml, get your PR approved and merged
```yaml
        - dnsName: src-serve-git-ubuntu.local
          listeningAddress: 100.100.100.0
          name: src-serve-git-ubuntu-local
          ports:
          - 80
        - dnsName: src-serve-git-wsl.local
          listeningAddress: 100.100.100.1
          name: src-serve-git-wsl-local
          ports:
          - 80
```
2. Run the Reload frontend GitHub Action, as this seems to be needed for the frontend pods to start using tunnel connections
3. Clone this repo to a customer's bridge VM, install Docker and Docker's Compose plugin
4. Copy the `config.yaml` and `service-account-key.json` files using the instructions on the instance's Cloud Ops dashboard
 - Paste them into `./config/cloud-agent-config.yaml` and `./config/cloud-agent-service-account-key.json`
5. Modify the `./config/cloud-agent-config.yaml` file
 - `serviceAccountKeyFile: /sourcegraph/cloud-agent-service-account-key.json` so that the Go binary inside the agent container finds this file in the path that's mapped via the docker-compose.yaml files
 - Only include the `- dialAddress` entries that this cloud agent instance can reach, remove the others, so the Cloud instance doesn't try using this agent instance for code hosts it can't reach
 - Correct open ports from the default `443` to `80` - this is the step I miss most often, leading to network errors showing in the Cloud instance's code host config, and agent container logs
 - Use extra caution when pasting the config.yaml in Windows, as it may use Windows' line endings or extra spaces, which breaks YAML, as a whitespace-dependent format
6. Clone the customer's repos into the `repos-to-serve` directory at the root of this repo on the bridge VM, or update the volume mount path for the src-serve-git service in the docker-compose.yaml file
7. Run `docker compose up -d`
8. Add a Code Host config to the customer's Cloud instance
 - Type: src serve-git
 - URL: "http://src-serve-git-ubuntu.local:80"
 - or
 - URL: "http://src-serve-git-wsl.local:80"
 - Note that the :80 port may be required, as this seems to default to port 443, even when used with http://
9. Use the repo-converter to convert SVN, TFVC, or Git repos, to Git format, which will store them in the `repos-to-serve` directory, or use any other means to get the repos into the directory
