#!/bin/bash

# function to start the UI
start_ui() {
  export PYTHONPATH=/usr/share/bunkerweb/deps/python/
  echo "Starting UI"
  set -a
  . /etc/bunkerweb/ui.env
  set +a
  #export FLASK_APP=/usr/share/bunkerweb/ui/main.py
  #python3 -m flask run --host=127.0.0.1 --port=7000
  python3 -m gunicorn --bind=0.0.0.0:7000 --workers=1 --threads=2 --user ui --group ui main:app
}

# function to stop the UI
stop_ui(){
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