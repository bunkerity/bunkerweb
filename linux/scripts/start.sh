#!/bin/bash

#############################################################
#                           Help                            #  
#############################################################
Help()
{
    # Dispaly Help
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
if [ ! -f /etc/sudoers.d/nginx ]; then
    echo "Adding nginx user to sudoers file ..."
    echo "nginx ALL=(ALL) NOPASSWD: /bin/systemctl restart bunkerweb" >> /etc/sudoers.d/nginx
    echo "Done !"
fi

#############################################################
#                           Checker                         #  
#############################################################

function check_ok() {
    if [ $? -eq 0 ]; then
        result="$?"
    else
        result="$?"
    fi
}

#############################################################
#                           Start                           #  
#############################################################

function start() {
    #############################################
    #                   STEP1                   #
    # Generate variables.env files to /tmp/     #
    #############################################
    printf "HTTP_PORT=80\nSERVER_NAME=example.com\nTEMP_NGINX=yes" > "/tmp/variables.env"
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Generate variables.env files to /tmp/"
    echo "OK !"
    #############################################
    #                   STEP2                   #
    # Generate first temporary config           #
    #############################################
    /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/variables.env
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Generate first temporary config"
    echo "OK !"
    #############################################
    #                   STEP3                   #
    #               Execute nginx               #
    #############################################
    nginx
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Execute nginx"
    echo "OK !"
    #############################################
    #                   STEP4                   #
    #               Run jobs script             #
    #############################################
    /opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env --run
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Run jobs script"
    echo "OK !"
    #############################################
    #                   STEP5                   #
    #                 Quit nginx                #
    ############################################# 
    nginx -s quit
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Quit nginx"
    echo "OK !"
    #############################################
    #                   STEP6                   #
    #           Generate final confs            #
    ############################################# 
    /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /opt/bunkerweb/variables.env
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Generate final confs"
    echo "OK !"
    #############################################
    #                   STEP7                   #
    #              Run jobs infinite            #
    ############################################# 
    /opt/bunkerweb/job/main.py --variables /etc/nginx/variables.env &
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Run jobs infinite"
    echo "OK !"
    #############################################
    #                   STEP8                   #
    #                Start nginx                #
    ############################################# 
    nginx -g "daemon off; user nginx;"
    # Test if command worked
    check_ok
    # Exit if failed
    if [ $result -ne 0 ];
    then
        echo "Your command exited with non-zero status $result"
        exit 1
    fi
    echo "Start nginx"
    echo "OK !"
}

function stop()
{
    echo "Stoping Bunkerweb service ..."
    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/opt/bunkerweb/tmp/scheduler.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        var=$( cat $PID_FILE_PATH )
        kill -SIGINT $var
        echo "Killing : $var"
    else
        echo "File doesn't exist"
    fi

    # Check if nginx running and if so, stop it
    SERVICE="nginx"
    if pgrep -x "$SERVICE" >/dev/null
    then
        echo "Stopping $SERVICE service"
        nginx -s stop
    else
        echo "$SERVICE already stopped"
    fi
    echo "Done !"
}

function reload()
{
    echo "Reloading Bunkerweb service ..."
    # Check if pid file exist and remove it if so
    PID_FILE_PATH="/opt/bunkerweb/tmp/scheduler.pid"
    if [ -f "$PID_FILE_PATH" ];
    then
        var=$( cat $PID_FILE_PATH )
        kill -SIGHUP $var
        echo "Reloading : $var"
    else
        echo "File doesn't exist"
    fi

    # Check if nginx running and if so, reload it
    SERVICE="nginx"
    if pgrep -x "$SERVICE" >/dev/null
    then
        echo "Reloading $SERVICE service"
        nginx -s reload
    else
        echo "$SERVICE already stopped"
    fi
    echo "Done !"
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
    Help
esac
