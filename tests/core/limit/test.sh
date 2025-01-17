#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🎚️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🎚️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🎚️ Building limit stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🎚️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "BAD_BEHAVIOR_STATUS_CODES=400 401 403 405 429 444" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_LIMIT_REQ=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "LIMIT_REQ_URL=/" | sudo tee -a /etc/bunkerweb/variables.env
    echo "LIMIT_REQ_RATE=2r/s" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_LIMIT_CONN=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "LIMIT_CONN_MAX_HTTP1=1" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_REQ: "yes"@USE_LIMIT_REQ: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@LIMIT_REQ_URL: ".*"$@LIMIT_REQ_URL: "/"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@LIMIT_REQ_RATE: ".*"$@LIMIT_REQ_RATE: "2r/s"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_CONN: "no"@USE_LIMIT_CONN: "yes"@' {} \;

            if [[ $(sed '33!d' docker-compose.yml) = '      LIMIT_REQ_URL_1: "/custom"' ]] ; then
                sed -i '33d' docker-compose.yml
            fi

            if [[ $(sed '33!d' docker-compose.yml) = '      LIMIT_REQ_RATE_1: "4r/s"' ]] ; then
                sed -i '33d' docker-compose.yml
            fi

            if [[ $(sed '11!d' docker-compose.test.yml) = '      LIMIT_REQ_URL_1: "/custom"' ]] ; then
                sed -i '11d' docker-compose.test.yml
            fi

            if [[ $(sed '11!d' docker-compose.test.yml) = '      LIMIT_REQ_RATE_1: "4r/s"' ]] ; then
                sed -i '11d' docker-compose.test.yml
            fi
        else
            sudo sed -i 's@USE_LIMIT_REQ=.*$@USE_LIMIT_REQ=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@LIMIT_REQ_URL=.*$@LIMIT_REQ_URL=/@' /etc/bunkerweb/variables.env
            sudo sed -i 's@LIMIT_REQ_RATE=.*$@LIMIT_REQ_RATE=2r/s@' /etc/bunkerweb/variables.env
            sudo sed -i 's@USE_LIMIT_CONN=.*$@USE_LIMIT_CONN=yes@' /etc/bunkerweb/variables.env
            unset USE_LIMIT_REQ
            unset LIMIT_REQ_URL
            unset LIMIT_REQ_RATE
            unset USE_LIMIT_CONN

            if [[ $(sudo tail -n 1 /etc/bunkerweb/variables.env) = 'LIMIT_REQ_URL_1=/custom' ]] ; then
                sudo truncate -s -1 /etc/bunkerweb/variables.env
            fi

            if [[ $(sudo tail -n 1 /etc/bunkerweb/variables.env) = 'LIMIT_REQ_RATE_1=4r/s' ]] ; then
                sudo truncate -s -1 /etc/bunkerweb/variables.env
            fi

            unset LIMIT_REQ_URL_1
            unset LIMIT_REQ_RATE_1
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🎚️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🎚️ Cleanup failed ❌"
        exit 1
    fi

    echo "🎚️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "http1" "limit_req" "augmented" "custom_endpoint_rate" "deactivated_req"
do
    if [ "$test" = "http1" ] ; then
        echo "🎚️ Running tests with limit conn activated and the limit conn max http1 set to 1 ..."
    elif [ "$test" = "limit_req" ] ; then
        echo "🎚️ Running tests with limit req activated ..."
        echo "ℹ️ Deactivating limit conn ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_CONN: "yes"@USE_LIMIT_CONN: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_REQ: "no"@USE_LIMIT_REQ: "yes"@' {} \;
        else
            sudo sed -i 's@USE_LIMIT_CONN=.*$@USE_LIMIT_CONN=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@USE_LIMIT_REQ=.*$@USE_LIMIT_REQ=yes@' /etc/bunkerweb/variables.env
            export USE_LIMIT_CONN="no"
            export USE_LIMIT_REQ="yes"
        fi
    elif [ "$test" = "augmented" ] ; then
        echo "🎚️ Running tests with limit req rate set to 10r/s ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@LIMIT_REQ_RATE: ".*"$@LIMIT_REQ_RATE: "10r/s"@' {} \;
        else
            sudo sed -i 's@LIMIT_REQ_RATE=.*$@LIMIT_REQ_RATE=10r/s@' /etc/bunkerweb/variables.env
            export LIMIT_REQ_RATE="10r/s"
        fi
    elif [ "$test" = "custom_endpoint_rate" ] ; then
        echo "🎚️ Running tests with a custom endpoint rate ..."
        if [ "$integration" == "docker" ] ; then
            sed -i '33i \      LIMIT_REQ_URL_1: "/custom"' docker-compose.yml
            sed -i '34i \      LIMIT_REQ_RATE_1: "4r/s"' docker-compose.yml
            sed -i '11i \      LIMIT_REQ_URL_1: "/custom"' docker-compose.test.yml
            sed -i '12i \      LIMIT_REQ_RATE_1: "4r/s"' docker-compose.test.yml
        else
            echo "LIMIT_REQ_URL_1=/custom" | sudo tee -a /etc/bunkerweb/variables.env
            echo "LIMIT_REQ_RATE_1=4r/s" | sudo tee -a /etc/bunkerweb/variables.env
            export LIMIT_REQ_URL_1="/custom"
            export LIMIT_REQ_RATE_1="4r/s"
        fi
    elif [ "$test" = "deactivated_req" ] ; then
        echo "🎚️ Running tests without limit req ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_REQ: "yes"@USE_LIMIT_REQ: "no"@' {} \;
        else
            sudo sed -i 's@USE_LIMIT_REQ=.*$@USE_LIMIT_REQ=no@' /etc/bunkerweb/variables.env
            export USE_LIMIT_REQ="no"
        fi
    fi

    echo "🎚️ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🎚️ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🎚️ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🎚️ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🎚️ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("limit-bw-1" "limit-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🎚️ Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🎚️ Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🎚️ Linux stack is healthy ✅"
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
                echo "🎚️ Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🎚️ ⚠ Linux stack got an issue, restarting ..."
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
            echo "🎚️ Linux stack could not be healthy ❌"
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
        echo "🎚️ Test \"$test\" failed ❌"
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
        echo "🎚️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🎚️ Tests are done ! ✅"
