#!/bin/bash

# If the environment variable wasn't provided by the user, configure a default schedule of hourly
if [[ -z $BRIDGE_REPO_CONVERTER_INTERVAL_MINUTES ]]
then
    BRIDGE_REPO_CONVERTER_INTERVAL_MINUTES=60
fi

# Write environment variables to where cron will use them
env >> /etc/environment

# Ensure the script is executable
chmod 744 /sourcegraph/run.py

# Write the cronjob to a file
echo "*/$BRIDGE_REPO_CONVERTER_INTERVAL_MINUTES * * * * python3 /sourcegraph/run.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/cron.d/repo-conversion-crontab
echo "" >> /etc/cron.d/repo-conversion-crontab

# Make the file readable
chmod 644 /etc/cron.d/repo-conversion-crontab

# Create the log file if it doesn't already exist
touch /var/log/cron.log

# Install the cronjob
crontab -r > /dev/null 2>&1
crontab /etc/cron.d/repo-conversion-crontab

# Start the script
python3 /sourcegraph/run.py

# Run cron, to keep the Docker container running
cron -f
