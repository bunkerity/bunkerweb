#! /bin/sh

# A shell option that causes the shell to exit immediately if a command exits with a non-zero status.
set -e

# if purge is called, we want to remove the old config file from the system
# if it exists

if [ "$1" = "purge" ]; then
    # purge bunkerweb 
    sudo systemctl stop bunkerweb
    sudo systemctl disable bunkerweb
    sudo rm -rf /opt/bunkerweb/
    sudo rm -rf /etc/systemd/system/bunkerweb.service
    sudo rm -rf /etc/systemd/system/bunkerweb-ui.service

    # reload unit files
    sudo systemctl daemon-reload
fi
