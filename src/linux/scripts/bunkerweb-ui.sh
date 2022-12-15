#!/bin/bash

export PYTHONPATH=/usr/share/bunkerweb/deps/python

# function to start the UI
start() {
  echo "Starting UI"
  python3 -m gunicorn --bind=0.0.0.0:7000 --chdir /usr/share/bunkerweb/ui/ --workers=1 --threads=2 --user scheduler --group scheduler main:app
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
        echo "Usage: ./bunkerweb-ui.sh start|stop|reload"
        ;;
    esac