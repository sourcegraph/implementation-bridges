# Run the Sourcegraph Cloud Private Connect Agent and src serve-git together in a Docker Compose file

## Experimental - This is not a supported Sourcegraph product
This repo was created for Sourcegraph Implementation Engineering deployments, and is not intended, designed, built, or supported for use in any other scenario. Feel free to open issues or PRs, but responses are best effort.

## Why
Running src serve-git and the agent together on the same Docker network allows the agent to use Docker's DNS to reach src serve-git, and prevents src serve-git's unauthenticated HTTP endpoint from needing to be opened outside of the Docker host.

Docker compose also allows for easier upgrades, troubleshooting, monitoring, logging, flexibility of hosting, etc.

## Setup - Sourcegraph Staff Only
1. Add the entry to the sourcegraphConnect targetGroups list in the Cloud instance's config.yaml, get your PR approved and merged
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
2. Clone this repo to a customer's bridge VM, install Docker and Docker's Compose plugin
3. Copy the config.yaml and service-account-key.json files from the Cloud Ops dashboard, and paste them in the files under the config directory
4. Modify the config.yaml copied from the Cloud Ops dashboard
 - `  serviceAccountKeyFile: /service-account-key.json` so that the Go binary inside the running Docker container finds this file in the path that's mapped via the docker-compose.yaml file
 - Only include the `- dialAddress` entries that this cloud agent can reach, remove the others, so the Cloud instance doesn't try connecting to this instance for code hosts it can't reach
 - Correct open ports from default 443 to 80
 - Careful when pasting the config.yaml into Windows, because it may add weird line endings or extra spaces, which breaks YAML, as a whitespace-dependent format
5. Clone the customer's repos into the `repos-to-serve` directory at the root of this repo on the bridge VM, or update the volume mount path for the src-serve-git service in the docker-compose.yaml file
6. docker compose up -d
7. Add a Code Host config to the customer's instance
 - Type: src serve-git
 - URL: "http://src-serve-git-ubuntu.local:80"
 - or
 - URL: "http://src-serve-git-wsl.local:80"
 - Note that the :80 port is required, as this seems to default to port 443, even when used with http://
8. Use the bridge-repo-converter to convert SVN, TFVC, or Git repos, to Git format, which will store them in the `repos-to-serve` directory, or use any other means at your disposal to get the repos into the /`repos-to-serve` directory
