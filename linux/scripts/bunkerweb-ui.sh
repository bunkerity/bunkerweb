#!/bin/bash

# function to start the UI
start_ui() {
  export PYTHONPATH=/opt/bunkerweb/deps/python/
  echo "Starting UI"
  set -a
  . /opt/bunkerweb/bunkerweb-ui.env
  set +a
  export FLASK_APP=/opt/bunkerweb/ui/main.py
  python3 -m flask run --host=127.0.0.1 --port=7000
}

# function to stop the UI
stop_ui(){
    echo "Stoping ui service ..."
    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/opt/bunkerweb/tmp/ui.pid"
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
reload_ui() {
  stop_ui
  # Wait for ui to stop
  sleep 5
  start_ui
  # if previous command worked then exit with 0
  exit 0
}

case "$1" in
    start)
        start_ui
        ;;
    stop)
        stop_ui
        ;;
    reload)
        reload_ui
        ;;
    *)
        echo "Usage: ./bunkerweb-ui.sh start|stop|reload"
        ;;
    esac