#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "⭕ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "⭕ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "⭕ Building errors stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⭕ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "ERRORS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "INTERCEPTED_ERROR_CODES=400 401 403 404 405 413 429 500 501 502 503 504" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    sudo mkdir -p /var/www/html/errors
    sudo cp "403.html" "/var/www/html/errors/403.html"
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ERRORS: "403=/errors/403.html"@ERRORS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"@INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"@' {} \;
        else
            sudo sed -i 's@ERRORS=.*$@ERRORS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@INTERCEPTED_ERROR_CODES=.*$@INTERCEPTED_ERROR_CODES=400 401 403 404 405 413 429 500 501 502 503 504@' /etc/bunkerweb/variables.env
            unset ERRORS
            unset INTERCEPTED_ERROR_CODES
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "⭕ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "⭕ Cleanup failed ❌"
        exit 1
    fi

    echo "⭕ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "default" "custom_403" "without_403"
do
    if [ "$test" = "default" ] ; then
        echo "⭕ Running tests with default configuration ..."
    elif [ "$test" = "custom_403" ] ; then
        echo "⭕ Running tests with a custom 403 page ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ERRORS: ""@ERRORS: "403=/errors/403.html"@' {} \;
        else
            sudo sed -i 's@ERRORS=@ERRORS=403=/errors/403.html@' /etc/bunkerweb/variables.env
            export ERRORS="403=/errors/403.html"
        fi
    elif [ "$test" = "without_403" ] ; then
        echo "⭕ Running tests without a 403 being intercepted ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ERRORS: "403=/errors/403.html"@ERRORS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"@INTERCEPTED_ERROR_CODES: "400 401 404 405 413 429 500 501 502 503 504"@' {} \;
        else
            sudo sed -i 's@ERRORS=.*$@ERRORS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@INTERCEPTED_ERROR_CODES=.*$@INTERCEPTED_ERROR_CODES=400 401 404 405 413 429 500 501 502 503 504@' /etc/bunkerweb/variables.env
            unset ERRORS
            export INTERCEPTED_ERROR_CODES="400 401 404 405 413 429 500 501 502 503 504"
        fi
    fi

    echo "⭕ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "⭕ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "⭕ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "⭕ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "⭕ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("errors-bw-1" "errors-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "⭕ Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "⭕ Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "⭕ Linux stack is healthy ✅"
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
                echo "⭕ Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "⭕ ⚠ Linux stack got an issue, restarting ..."
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
            echo "⭕ Linux stack could not be healthy ❌"
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
        echo "⭕ Test \"$test\" failed ❌"
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
        echo "⭕ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "⭕ Tests are done ! ✅"
