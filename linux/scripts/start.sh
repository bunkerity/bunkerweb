#!/bin/bash

. /usr/share/bunkerweb/helpers/utils.sh

#############################################################
#                           Help                            #  
#############################################################
function display_help()
{
    # Display Help
    echo "Usage of this script"
    echo 
    echo "Syntax: start [start|stop|reload]"
    echo "options:"
    echo "start     Create the configurations file and run all the jobs needed throught the bunkerweb service."
    echo "stop      Stop the bunkerweb service."
    echo "reload    Reload the bunkerweb service"
    echo
}

export PYTHONPATH=/usr/share/bunkerweb/deps/python/

# Add nginx to sudoers
if [ ! -f /etc/sudoers.d/bunkerweb ]; then
    log "ENTRYPOINT" "ℹ️" "Adding nginx user to sudoers ..."
    echo "nginx ALL=(ALL) NOPASSWD: /bin/systemctl restart bunkerweb" > /etc/sudoers.d/bunkerweb
fi

#############################################################
#                           Start                           #  
#############################################################

function start() {

    # Get the pid of nginx and put it in a file
    log "ENTRYPOINT" "ℹ️" "Getting nginx pid ..."
    nginx_pid=$(ps aux | grep nginx | awk '{print $2}')
    echo $nginx_pid > /var/tmp/bunkerweb/nginx.pid

    ps -ef | grep nginx | grep -v grep | awk '{print $2}' > /var/tmp/bunkerweb/nginx.pid

    if [ -f /var/tmp/bunkerweb/scheduler.pid ] ; then
        rm -f /var/tmp/bunkerweb/scheduler.pid
    fi

    # setup and check /data folder
    /usr/share/bunkerweb/helpers/data.sh "ENTRYPOINT"

    # trap SIGTERM and SIGINT
    function trap_exit() {
        log "ENTRYPOINT" "ℹ️ " "Catched stop operation"
        if [ -f "/var/tmp/bunkerweb/scheduler.pid" ] ; then
            log "ENTRYPOINT" "ℹ️ " "Stopping job scheduler ..."
            kill -s TERM "$(cat /var/rmp/bunkerweb/scheduler.pid)"
        fi
    }
    trap "trap_exit" TERM INT QUIT

    # trap SIGHUP
    function trap_reload() {
        log "ENTRYPOINT" "ℹ️ " "Catched reload operation"
        /usr/share/bunkerweb/helpers/scheduler-restart.sh
        if [ $? -ne 0 ] ; then
            log "ENTRYPOINT" "ℹ️ " "Error while restarting scheduler"
        fi
    }
    trap "trap_reload" HUP

    # Init database
    # generate "temp" config
    #get_env > "/tmp/variables.env"
    echo -e "IS_LOADING=yes\nSERVER_NAME=\nAPI_HTTP_PORT=${API_HTTP_PORT:-5000}\nAPI_SERVER_NAME=${API_SERVER_NAME:-bwapi}\nAPI_WHITELIST_IP=${API_WHITELIST_IP:-127.0.0.0/8}" > /tmp/variables.env
    /usr/share/bunkerweb/gen/save_config.py --variables /tmp/variables.env --init
    if [ "$?" -ne 0 ] ; then
        log "ENTRYPOINT" "❌" "Scheduler generator failed"
        exit 1
    fi

    generate=yes
    if [ -f "/etc/nginx/variables.env" ] && grep -q "^IS_LOADING=no$" /etc/nginx/variables.env ; then
        log "ENTRYPOINT" "⚠️ " "Looks like BunkerWeb configuration is already generated, will not generate it again"
        generate=no
    fi

    # execute jobs
    log "ENTRYPOINT" "ℹ️ " "Executing scheduler ..."
    /usr/share/bunkerweb/scheduler/main.py --generate $generate

    log "ENTRYPOINT" "ℹ️ " "Scheduler stopped"
    exit 0
}

function stop()
{
	ret=0
    log "ENTRYPOINT" "ℹ️" "Stopping BunkerWeb service ..."
	
    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/var/rmp/bunkerweb/scheduler.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        var=$(cat "$PID_FILE_PATH")
		log "ENTRYPOINT" "ℹ️" "Sending stop signal to scheduler ..."
        kill -SIGINT $var
		result=$?
		if [ $result -ne 0 ] ; then
			log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
			exit 1
		fi
    else
        log "ENTRYPOINT" "❌" "Scheduler is not running"
		ret=1
    fi

    # Check if nginx running and if so, stop it
    SERVICE="nginx"
    if pgrep -x "$SERVICE" > /dev/null
    then
        log "ENTRYPOINT" "ℹ️" "Sending stop signal to BunkerWeb ..."
        nginx -s quit
		result=$?
		if [ $result -ne 0 ] ; then
			log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
			exit 1
		fi
    else
        log "ENTRYPOINT" "❌" "BunkerWeb is not running"
		exit 1
    fi
	exit $ret
}

function reload()
{
    log "ENTRYPOINT" "ℹ️" "Reloading BunkerWeb service ..."

    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/var/tmp/bunkerweb/scheduler.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        var=$(cat "$PID_FILE_PATH")
		log "ENTRYPOINT" "ℹ️" "Sending reload signal to scheduler ..."
        kill -SIGHUP $var
		result=$?
		if [ $result -ne 0 ] ; then
			log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
			exit 1
		fi
    else
        log "ENTRYPOINT" "❌" "Scheduler is not running"
		exit 1
    fi

    # Check if nginx running and if so, reload it
    SERVICE="nginx"
    if pgrep -x "$SERVICE" > /dev/null
    then
        log "ENTRYPOINT" "ℹ️" "Sending reload signal to BunkerWeb ..."
        nginx -s reload
		result=$?
		if [ $result -ne 0 ] ; then
			log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
			exit 1
		fi
    else
        log "ENTRYPOINT" "❌" "BunkerWeb is not running"
		exit 1
    fi
}

# List of differents args
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
    echo "Invalid option!"
    echo "List of options availables:"
    display_help
esac
