#!/bin/bash
#
# A shell option that causes the shell to exit immediately if a command exits with a non-zero status.
set -e
#
# function to stop bunkerweb
function stopBunker()
{
    echo "Stopping Bunkerweb service ..."
    # Stop bunkerweb service
    systemctl stop bunkerweb
}

function stopUI()
{
    echo "Stopping bunkerweb-ui service ..."
    # Stop flask server
    systemctl stop bunkerweb-ui
    echo "Done !"
}
#
# Check if bunkerweb service is running
if systemctl is-active --quiet bunkerweb; then
    # Stop bunkerweb service
    stopBunker
fi
# Check if bunkerweb-ui service is running
if systemctl is-active --quiet bunkerweb-ui; then
    # Stop ui service
    stopUI
fi
