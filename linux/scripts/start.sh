#!/bin/bash

. /opt/bunkerweb/helpers/utils.sh

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

export PYTHONPATH=/opt/bunkerweb/deps/python/

# Add nginx to sudoers
if [ ! -f /etc/sudoers.d/bunkerweb ]; then
    log "ENTRYPOINT" "ℹ️" "Adding nginx user to sudoers ..."
    echo "nginx ALL=(ALL) NOPASSWD: /bin/systemctl restart bunkerweb" > /etc/sudoers.d/bunkerweb
fi

#############################################################
#                           Start                           #  
#############################################################

function start() {
    #############################################
    #                   STEP1                   #
    # Generate variables.env files to /tmp/     #
    #############################################
	log "ENTRYPOINT" "ℹ️" "Generate variables.env files to /tmp/ ..."
    printf "HTTP_PORT=80\nSERVER_NAME=example.com\nTEMP_NGINX=yes" > "/tmp/variables.env"
    result=$?
	if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi

    #############################################
    #                   STEP2                   #
    # Generate first temporary config           #
    #############################################
	log "ENTRYPOINT" "ℹ️" "Generate temporary config ..."
    /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/variables.env
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi

    #############################################
    #                   STEP3                   #
    #               Execute nginx               #
    #############################################
    log "ENTRYPOINT" "ℹ️" "Execute temporary BunkerWeb ..."
	nginx
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi    

    #############################################
    #                   STEP4                   #
    #               Run jobs script             #
    #############################################
	log "ENTRYPOINT" "ℹ️" "Run jobs once ..."
    /opt/bunkerweb/job/main.py --variables /opt/bunkerweb/variables.env --run
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi

    #############################################
    #                   STEP5                   #
    #                 Quit nginx                #
    ############################################# 
    log "ENTRYPOINT" "ℹ️" "Stop temporary BunkerWeb ..."
	nginx -s quit
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi

    #############################################
    #                   STEP6                   #
    #           Generate final confs            #
    #############################################
	log "ENTRYPOINT" "ℹ️" "Generate final config ..."
    /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /opt/bunkerweb/variables.env
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi

    #############################################
    #                   STEP7                   #
    #              Run jobs infinite            #
    #############################################
	log "ENTRYPOINT" "ℹ️" "Run jobs scheduler ..."
    /opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env &
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi

    #############################################
    #                   STEP8                   #
    #                Start nginx                #
    #############################################
	log "ENTRYPOINT" "ℹ️" "Start BunkerWeb ..."
    nginx -g "daemon off; user nginx;"
    result=$?
    if [ $result -ne 0 ];
    then
        log "ENTRYPOINT" "❌" "Your command exited with non-zero status $result"
        exit 1
    fi
}

function stop()
{
	ret=0
    log "ENTRYPOINT" "ℹ️" "Stopping BunkerWeb service ..."
	
    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/opt/bunkerweb/tmp/scheduler.pid"
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
    PID_FILE_PATH="/opt/bunkerweb/tmp/scheduler.pid"
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
    echo "List of option available:"
    display_help
esac
