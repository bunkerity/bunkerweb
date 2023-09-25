#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "Integration \"$integration\" is not supported ❌"
    exit 1
fi

# Prepare environment
if [ "$integration" = "docker" ] ; then
    sed -i "s@bunkerity/bunkerweb:.*@bunkerweb-tests@" docker-compose.yml
    sed -i "s@bunkerity/bunkerweb-scheduler:.*@scheduler-tests@" docker-compose.yml
    sed -i "s@bunkerity/bunkerweb-ui:.*@ui-tests@" docker-compose.yml

    # Start stack
    docker-compose pull bw-docker-proxy app1
    if [ $? -ne 0 ] ; then
        echo "❌ Pull failed"
        exit 1
    fi

    echo "🤖 Starting stack ..."
    docker compose up -d
    if [ $? -ne 0 ] ; then
        echo "🤖 Up failed, retrying ... ⚠️"
        docker compose down -v --remove-orphans
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🤖 Up failed ❌"
            exit 1
        fi
    fi
else
    sudo systemctl stop bunkerweb bunkerweb-ui
    sudo sed -i "/python3 -m gunicorn/c\    python3 -m flask --app main:app run --host=127.0.0.1 --port=7000 &" /usr/share/bunkerweb/scripts/bunkerweb-ui.sh
    export MAKEFLAGS="-j$(nproc)"
    pip install --force-reinstall --no-cache-dir --require-hashes --target /usr/share/bunkerweb/deps/python -r /usr/share/bunkerweb/deps/requirements.txt
    sudo chown -R nginx:nginx /usr/share/bunkerweb
    find /usr/share/bunkerweb -path /usr/share/bunkerweb/ui/deps -prune -o -type f -exec sudo chmod 0740 {} \;
    find /usr/share/bunkerweb -path /usr/share/bunkerweb/ui/deps -prune -o -type d -exec sudo chmod 0750 {} \;
    sudo mkdir /var/www/html/app1.example.com
    sudo touch /var/www/html/app1.example.com/index.html
    export TEST_TYPE="linux"
fi

i=0
if [ "$integration" == "docker" ] ; then
    while [ $i -lt 120 ] ; do
        containers=("ui-bw-1" "ui-bw-scheduler-1" "ui-bw-ui-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                echo "⚠️ Container $container is not healthy yet ..."
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker-compose logs
        echo "❌ Docker stack is not healthy"
        exit 1
    fi
else
    sudo systemctl start bunkerweb bunkerweb-ui
    healthy="false"
    retries=0
    while [[ $healthy = "false" && $retries -lt 5 ]] ; do
        while [ $i -lt 120 ] ; do
            if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                echo "🔏 Linux stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            echo "🛡️ Showing BunkerWeb journal logs ..."
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb UI journal logs ..."
            sudo journalctl -u bunkerweb-ui --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
            echo "🔏 Linux stack is not healthy ❌"
            exit 1
        fi

        if ! [ -z "$(sudo journalctl -u bunkerweb --no-pager | grep "SYSTEMCTL - ❌")" ] ; then
            echo "🔏 ⚠ Linux stack got an issue, restarting ..."
            sudo journalctl --rotate
            sudo journalctl --vacuum-time=1s
            manual=1
            cleanup_stack
            manual=0
            sudo systemctl start bunkerweb
            retries=$((retries+1))
        else
            healthy="true"
        fi
    done
    if [ $retries -ge 5 ] ; then
        echo "🔏 Linux stack could not be healthy ❌"
        exit 1
    fi
fi

# Start tests
if [ "$integration" == "docker" ] ; then
    docker-compose -f docker-compose.test.yml build
    if [ $? -ne 0 ] ; then
        echo "❌ Build failed"
        exit 1
    fi

    docker-compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from ui-tests
else
    python3 main.py
fi

if [ $? -ne 0 ] ; then
    if [ "$integration" == "docker" ] ; then
        docker compose logs
    else
        echo "🛡️ Showing BunkerWeb journal logs ..."
        sudo journalctl -u bunkerweb --no-pager
        echo "🛡️ Showing BunkerWeb UI journal logs ..."
        sudo journalctl -u bunkerweb-ui --no-pager
        echo "🛡️ Showing BunkerWeb error logs ..."
        sudo cat /var/log/bunkerweb/error.log
        echo "🛡️ Showing BunkerWeb access logs ..."
        sudo cat /var/log/bunkerweb/access.log
        echo "🛡️ Showing Geckodriver logs ..."
        sudo cat geckodriver.log
    fi
    echo "❌ Tests failed"
    exit 1
fi

# Exit
exit 0
