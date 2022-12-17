#!/bin/bash

export PYTHONPATH=/usr/share/bunkerweb/deps/python

# Create ui.env file if it doesn't exist 
if [ ! -f /etc/bunkerweb/ui.env ]; then
  # Creating a file called `ui.env` in the `/etc/bunkerweb` directory.
  echo -e "ADMIN_USERNAME=admin\nADMIN_PASSWORD=changeme\nABSOLUTE_URI=" > /etc/bunkerweb/ui.env
fi

# function to start the UI
start() {
  echo "Starting UI"
  python3 -m gunicorn --bind=127.0.0.1:7000 --chdir /usr/share/bunkerweb/ui/ --workers=1 --threads=2 --user scheduler --group scheduler main:app &
  # Source /etc/bunkerweb/ui.env to load variables
  source /etc/bunkerweb/ui.env
  # Export all variables to environment
  export $(cat /etc/bunkerweb/ui.env)
}

# function to stop the UI
stop(){
    echo "Stoping ui service ..."
    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/var/tmp/bunkerweb/ui.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        var=$( cat $PID_FILE_PATH )
        kill -SIGINT $var
        echo "Killing : $var"
    else
        echo "File doesn't exist"
    fi
}

# function reload the UI
reload() {
  stop_ui
  # Wait for ui to stop
  sleep 5
  start_ui
  # if previous command worked then exit with 0
  exit 0
}

case $1 in
    "start") 
    start
    ;;
    "stop") 
    stop
    ;;
    "reload") 
    reload
    ;;
    *)
        echo "Usage: ./bunkerweb-ui.sh start"
        ;;
    esac