# Run the Sourcegraph Cloud Private Connect Agent and src serve-git together in a Docker Compose file

## Why
Running src serve-git and the agent together on the same Docker network allows the agent to use Docker's DNS to reach src serve-git, and prevents src serve-git's unauthenticated HTTP endpoint from being reachable to other hosts on the bridge VM's network.

It also allows for easier upgrades

## Setup
1. Clone this repo to a customer's bridge VM
2. Copy the config.yaml and service-account-key.json files from the Cloud Ops dashboard, and paste them in the files under the config directory
3. Clone the customer's repos into the /sourcegraph/repos directory on the bridge VM, or update the volume mount path for the src-serve-git service in the docker-compose.yaml file
4. docker compose up -d
5. Add a Code Host config to the customer's instance
 - Type: src serve-git
 - URL: "http://src-serve-git:3434"
6. Profit
