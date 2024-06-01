#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "📟 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "📟 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "📟 Building badbehavior stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose pull bw-docker
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📟 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📟 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    MAKEFLAGS="-j $(nproc)" sudo pip install --ignore-installed --break-system-packages --no-cache-dir --require-hashes --no-deps -r requirements.txt
    echo "USE_BAD_BEHAVIOR=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BAD_BEHAVIOR_STATUS_CODES=400 401 403 404 405 429 444" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BAD_BEHAVIOR_BAN_TIME=86400" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BAD_BEHAVIOR_THRESHOLD=10" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BAD_BEHAVIOR_COUNT_TIME=60" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BAD_BEHAVIOR: "no"@USE_BAD_BEHAVIOR: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_STATUS_CODES: "400 401 404 405 429 444"@BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_BAN_TIME: "60"@BAD_BEHAVIOR_BAN_TIME: "86400"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_THRESHOLD: "20"@BAD_BEHAVIOR_THRESHOLD: "10"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_COUNT_TIME: "30"@BAD_BEHAVIOR_COUNT_TIME: "60"@' {} \;
        else
            sudo sed -i 's@USE_BAD_BEHAVIOR=.*$@USE_BAD_BEHAVIOR=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_STATUS_CODES=.*$@BAD_BEHAVIOR_STATUS_CODES=400 401 403 404 405 429 444@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_BAN_TIME=.*$@BAD_BEHAVIOR_BAN_TIME=86400@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_THRESHOLD=.*$@BAD_BEHAVIOR_THRESHOLD=10@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_COUNT_TIME=.*$@BAD_BEHAVIOR_COUNT_TIME=60@' /etc/bunkerweb/variables.env
            unset USE_BAD_BEHAVIOR
            unset BAD_BEHAVIOR_STATUS_CODES
            unset BAD_BEHAVIOR_BAN_TIME
            unset BAD_BEHAVIOR_THRESHOLD
            unset BAD_BEHAVIOR_COUNT_TIME
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "📟 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📟 Cleanup failed ❌"
        exit 1
    fi

    echo "📟 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "activated" "deactivated" "status_codes" "ban_time" "threshold" "count_time"
do
    if [ "$test" = "activated" ] ; then
        echo "📟 Running tests with badbehavior activated ..."
    elif [ "$test" = "deactivated" ] ; then
        echo "📟 Running tests without badbehavior ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BAD_BEHAVIOR: "yes"@USE_BAD_BEHAVIOR: "no"@' {} \;
        else
            sudo sed -i 's@USE_BAD_BEHAVIOR=.*$@USE_BAD_BEHAVIOR=no@' /etc/bunkerweb/variables.env
            export USE_BAD_BEHAVIOR="no"
        fi
    elif [ "$test" = "status_codes" ] ; then
        echo "📟 Running tests with badbehavior's 403 status code removed from the list ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BAD_BEHAVIOR: "no"@USE_BAD_BEHAVIOR: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"@BAD_BEHAVIOR_STATUS_CODES: "400 401 404 405 429 444"@' {} \;
        else
            sudo sed -i 's@USE_BAD_BEHAVIOR=.*$@USE_BAD_BEHAVIOR=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_STATUS_CODES=.*$@BAD_BEHAVIOR_STATUS_CODES=400 401 404 405 429 444@' /etc/bunkerweb/variables.env
            export USE_BAD_BEHAVIOR="yes"
            export BAD_BEHAVIOR_STATUS_CODES="400 401 404 405 429 444"
        fi
    elif [ "$test" = "ban_time" ] ; then
        echo "📟 Running tests with badbehavior's ban time changed to 60 seconds ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_STATUS_CODES: "400 401 404 405 429 444"@BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_BAN_TIME: "86400"@BAD_BEHAVIOR_BAN_TIME: "60"@' {} \;
        else
            sudo sed -i 's@BAD_BEHAVIOR_STATUS_CODES=.*$@BAD_BEHAVIOR_STATUS_CODES=400 401 403 404 405 429 444@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_BAN_TIME=.*$@BAD_BEHAVIOR_BAN_TIME=60@' /etc/bunkerweb/variables.env
            export BAD_BEHAVIOR_STATUS_CODES="400 401 403 404 405 429 444"
            export BAD_BEHAVIOR_BAN_TIME="60"
        fi
    elif [ "$test" = "threshold" ] ; then
        echo "📟 Running tests with badbehavior's threshold set to 20 ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_BAN_TIME: "60"@BAD_BEHAVIOR_BAN_TIME: "86400"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_THRESHOLD: "10"@BAD_BEHAVIOR_THRESHOLD: "20"@' {} \;
        else
            sudo sed -i 's@BAD_BEHAVIOR_BAN_TIME=.*$@BAD_BEHAVIOR_BAN_TIME=86400@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_THRESHOLD=.*$@BAD_BEHAVIOR_THRESHOLD=20@' /etc/bunkerweb/variables.env
            export BAD_BEHAVIOR_BAN_TIME="86400"
            export BAD_BEHAVIOR_THRESHOLD="20"
        fi
    elif [ "$test" = "count_time" ] ; then
        echo "📟 Running tests with badbehavior's count time set to 30 seconds ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_THRESHOLD: "20"@BAD_BEHAVIOR_THRESHOLD: "10"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BAD_BEHAVIOR_COUNT_TIME: "60"@BAD_BEHAVIOR_COUNT_TIME: "30"@' {} \;
        else
            sudo sed -i 's@BAD_BEHAVIOR_THRESHOLD=.*$@BAD_BEHAVIOR_THRESHOLD=10@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BAD_BEHAVIOR_COUNT_TIME=.*$@BAD_BEHAVIOR_COUNT_TIME=30@' /etc/bunkerweb/variables.env
            export BAD_BEHAVIOR_THRESHOLD="10"
            export BAD_BEHAVIOR_COUNT_TIME="30"
        fi
    fi

    echo "📟 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "📟 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "📟 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "📟 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "📟 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("badbehavior-bw-1" "badbehavior-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "📟 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "📟 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "📟 Linux stack is healthy ✅"
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
                echo "📟 Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "📟 ⚠ Linux stack got an issue, restarting ..."
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
            echo "📟 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests

    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
    else
        sudo -E python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📟 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        if [ "$integration" == "docker" ] ; then
            docker compose logs bw bw-scheduler
        else
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
        fi
        exit 1
    else
        echo "📟 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "📟 Tests are done ! ✅"
