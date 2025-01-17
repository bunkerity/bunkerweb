#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🛰️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🛰️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🛰️ Building cors stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose pull app1
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🛰️ Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🛰️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    sudo cp -r www/* /var/www/html/
    sudo chown -R www-data:nginx /var/www/html
    sudo find /var/www/html -type f -exec chmod 0640 {} \;
    sudo find /var/www/html -type d -exec chmod 0750 {} \;
    echo "LOCAL_PHP=/run/php/php-fpm.sock" | sudo tee -a /etc/bunkerweb/variables.env
    echo "LOCAL_PHP_PATH=/var/www/html" | sudo tee -a /etc/bunkerweb/variables.env
    echo "ALLOWED_METHODS=GET|POST|HEAD|OPTIONS" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GENERATE_SELF_SIGNED_SSL=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_CORS=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CORS_ALLOW_ORIGIN=*" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CORS_EXPOSE_HEADERS=Content-Length,Content-Range" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CORS_MAX_AGE=86400" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CORS_ALLOW_CREDENTIALS=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CORS_ALLOW_METHODS=GET, POST, OPTIONS" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CORS_ALLOW_HEADERS=DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range" | sudo tee -a /etc/bunkerweb/variables.env
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CORS: "yes"@USE_CORS: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: ".*"$@CORS_ALLOW_ORIGIN: "\*"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "X-Test"@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "3600"@CORS_MAX_AGE: "86400"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "yes"@CORS_ALLOW_CREDENTIALS: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_HEADERS: "X-Test"@CORS_ALLOW_HEADERS: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"@' {} \;
        else
            sudo sed -i 's@USE_CORS=.*$@USE_CORS=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_ORIGIN=.*$@CORS_ALLOW_ORIGIN=*@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_EXPOSE_HEADERS=.*$@CORS_EXPOSE_HEADERS=Content-Length,Content-Range@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_MAX_AGE=.*$@CORS_MAX_AGE=86400@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_CREDENTIALS=.*$@CORS_ALLOW_CREDENTIALS=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_METHODS=.*$@CORS_ALLOW_METHODS=GET, POST, OPTIONS@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_HEADERS=.*$@CORS_ALLOW_HEADERS=DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range@' /etc/bunkerweb/variables.env
            unset USE_CORS
            unset GENERATE_SELF_SIGNED_SSL
            unset CORS_ALLOW_ORIGIN
            unset CORS_EXPOSE_HEADERS
            unset CORS_MAX_AGE
            unset CORS_ALLOW_CREDENTIALS
            unset CORS_ALLOW_METHODS
            unset CORS_ALLOW_HEADERS
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🛰️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🛰️ Cleanup failed ❌"
        exit 1
    fi

    echo "🛰️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

if [ "$integration" == "docker" ] ; then
    echo "🛰️ Initializing workspace ..."
    docker compose -f docker-compose.init.yml up --build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🛰️ Build failed ❌"
        exit 1
    elif [[ $(stat -L -c "%a %g %u" www/app1.example.com/index.php) != "655 101 33" ]] ; then
        echo "🛰️ Init failed, permissions are not correct ❌"
        exit 1
    fi
fi

for test in "deactivated" "activated" "allow_origin" "tweaked_settings"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🛰️ Running tests without cors ..."
    elif [ "$test" = "activated" ] ; then
        echo "🛰️ Running tests with cors ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CORS: "no"@USE_CORS: "yes"@' {} \;
        else
            sudo sed -i 's@USE_CORS=.*$@USE_CORS=yes@' /etc/bunkerweb/variables.env
            export USE_CORS="yes"
        fi
    elif [ "$test" = "allow_origin" ] ; then
        echo "🛰️ Running tests with a specific origin allowed only ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: "\*"@CORS_ALLOW_ORIGIN: "^http://app1\\\\.example\\\\.com$$"@' {} \;
        else
            sudo sed -i 's@CORS_ALLOW_ORIGIN=.*$@CORS_ALLOW_ORIGIN=^http://app1\\.example\\.com$$@' /etc/bunkerweb/variables.env
            export CORS_ALLOW_ORIGIN="^http://app1\\.example\\.com\$"
        fi
    elif [ "$test" = "tweaked_settings" ] ; then
        echo "🛰️ Running tests with tweaked cors settings ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: ".*"$@CORS_ALLOW_ORIGIN: "^https://app1\\\\.example\\\\.com$$"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@CORS_EXPOSE_HEADERS: "X-Test"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "86400"@CORS_MAX_AGE: "3600"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "no"@CORS_ALLOW_CREDENTIALS: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_HEADERS: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"@CORS_ALLOW_HEADERS: "X-Test"@' {} \;
        else
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_ORIGIN=.*$@CORS_ALLOW_ORIGIN=^https://app1\\.example\\.com\$@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_EXPOSE_HEADERS=.*$@CORS_EXPOSE_HEADERS=X-Test@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_MAX_AGE=.*$@CORS_MAX_AGE=3600@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_CREDENTIALS=.*$@CORS_ALLOW_CREDENTIALS=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_METHODS=.*$@CORS_ALLOW_METHODS=GET, HEAD, POST, OPTIONS@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CORS_ALLOW_HEADERS=.*$@CORS_ALLOW_HEADERS=X-Test@' /etc/bunkerweb/variables.env
            export GENERATE_SELF_SIGNED_SSL="yes"
            export CORS_ALLOW_ORIGIN="^https://app1\\.example\\.com\$"
            export CORS_EXPOSE_HEADERS="X-Test"
            export CORS_MAX_AGE="3600"
            export CORS_ALLOW_CREDENTIALS="yes"
            export CORS_ALLOW_METHODS="GET, HEAD, POST, OPTIONS"
            export CORS_ALLOW_HEADERS="X-Test"
        fi
    fi

    echo "🛰️ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🛰️ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🛰️ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🛰️ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🛰️ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("cors-bw-1" "cors-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🛰️ Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🛰️ Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🛰️ Linux stack is healthy ✅"
                    break
                fi
                sleep 1
                i=$((i+1))
            done
            if [ $i -ge 120 ] ; then
                sudo journalctl -u bunkerweb --no-pager
                echo "🛡️ Showing BunkerWeb error logs ..."
                sudo cat /var/log/bunkerweb/error.log
                echo "🛡️ Showing BunkerWeb access logs ..."
                sudo cat /var/log/bunkerweb/access.log
                echo "🛰️ Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🛰️ ⚠ Linux stack got an issue, restarting ..."
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
        if [ "$retries" -ge 5 ] ; then
            echo "🛰️ Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests

    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
    else
        python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🛰️ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        if [ "$integration" == "docker" ] ; then
            docker compose logs bw bw-scheduler
        else
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
            echo "🛡️ Showing Geckodriver logs ..."
            sudo cat geckodriver.log
        fi
        exit 1
    else
        echo "🛰️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🛰️ Tests are done ! ✅"
