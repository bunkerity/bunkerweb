#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "↪️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "↪️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "↪️ Building reverseproxy stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose pull bw-docker
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "↪️ Pull failed ❌"
        exit 1
    fi

    echo "↪️ Building custom api image ..."
    docker compose build reverseproxy-api
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "↪️ Build failed ❌"
        exit 1
    fi

    echo "↪️ Building test image ..."
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "↪️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "LIMIT_REQ_RATE=20r/s" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_REVERSE_PROXY=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_INTERCEPT_ERRORS=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_HOST=http://127.0.0.1:8080" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_URL=/" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_WS=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_HEADERS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_HEADERS_CLIENT=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_KEEPALIVE=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_AUTH_REQUEST=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_AUTH_REQUEST_SET=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_PROXY_CUSTOM_HOST=" | sudo tee -a /etc/bunkerweb/variables.env
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_PROXY: "yes"@USE_REVERSE_PROXY: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_INTERCEPT_ERRORS: "no"@REVERSE_PROXY_INTERCEPT_ERRORS: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_WS: "yes"@REVERSE_PROXY_WS: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_HEADERS: ".*"@REVERSE_PROXY_HEADERS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_HEADERS_CLIENT: ".*"@REVERSE_PROXY_HEADERS_CLIENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_KEEPALIVE: "yes"@REVERSE_PROXY_KEEPALIVE: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_AUTH_REQUEST: ".*"@REVERSE_PROXY_AUTH_REQUEST: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: ".*"@REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_AUTH_REQUEST_SET: ".*"@REVERSE_PROXY_AUTH_REQUEST_SET: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_CUSTOM_HOST: ".*"@REVERSE_PROXY_CUSTOM_HOST: ""@' {} \;
        else
            x=13
            while [ $x -gt 0 ] ; do
                sudo sed -i '$ d' /etc/bunkerweb/variables.env
                x=$((x-1))
            done
            unset USE_REVERSE_PROXY
            unset REVERSE_PROXY_INTERCEPT_ERRORS
            unset REVERSE_PROXY_WS
            unset REVERSE_PROXY_HEADERS
            unset REVERSE_PROXY_HEADERS_CLIENT
            unset REVERSE_PROXY_KEEPALIVE
            unset REVERSE_PROXY_AUTH_REQUEST
            unset REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL
            unset REVERSE_PROXY_AUTH_REQUEST_SET
            unset REVERSE_PROXY_CUSTOM_HOST
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "↪️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo killall python3
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "↪️ Cleanup failed ❌"
        exit 1
    fi

    echo "↪️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "deactivated" "activated" "websocket_keepalive" "tweaked" # TODO: auth_signin
do
    if [ "$test" = "deactivated" ] ; then
        echo "↪️ Running tests without reverseproxy ..."
    elif [ "$test" = "activated" ] ; then
        echo "↪️ Running tests with reverseproxy activated ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_PROXY: "no"@USE_REVERSE_PROXY: "yes"@' {} \;
        else
            sudo sed -i 's@USE_REVERSE_PROXY=no$@USE_REVERSE_PROXY=yes@' /etc/bunkerweb/variables.env
            export USE_REVERSE_PROXY="yes"
        fi
    elif [ "$test" = "websocket_keepalive" ] ; then
        echo "↪️ Running tests with reverseproxy activated, websocket and keepalive ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_WS: "no"@REVERSE_PROXY_WS: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_KEEPALIVE: "no"@REVERSE_PROXY_KEEPALIVE: "yes"@' {} \;
        else
            sudo sed -i 's@REVERSE_PROXY_WS=no$@REVERSE_PROXY_WS=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_KEEPALIVE=no$@REVERSE_PROXY_KEEPALIVE=yes@' /etc/bunkerweb/variables.env
            export REVERSE_PROXY_WS="yes"
            export REVERSE_PROXY_KEEPALIVE="yes"
        fi
    elif [ "$test" = "tweaked" ] ; then
        echo "↪️ Running tests with tweaked reverseproxy settings ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_WS: "yes"@REVERSE_PROXY_WS: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_KEEPALIVE: "yes"@REVERSE_PROXY_KEEPALIVE: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_INTERCEPT_ERRORS: "yes"@REVERSE_PROXY_INTERCEPT_ERRORS: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_HEADERS: ".*"@REVERSE_PROXY_HEADERS: "Test test;Test2 test2"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_HEADERS_CLIENT: ".*"@REVERSE_PROXY_HEADERS_CLIENT: "Test test;Test2 test2"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_AUTH_REQUEST: ".*"@REVERSE_PROXY_AUTH_REQUEST: "/auth"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_CUSTOM_HOST: ".*"@REVERSE_PROXY_CUSTOM_HOST: "test.example.com"@' {} \;
        else
            sudo sed -i 's@REVERSE_PROXY_WS=yes$@REVERSE_PROXY_WS=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_KEEPALIVE=yes$@REVERSE_PROXY_KEEPALIVE=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_INTERCEPT_ERRORS=yes$@REVERSE_PROXY_INTERCEPT_ERRORS=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_HEADERS=.*$@REVERSE_PROXY_HEADERS=Test test;Test2 test2@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_HEADERS_CLIENT=.*$@REVERSE_PROXY_HEADERS_CLIENT=Test test;Test2 test2@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_AUTH_REQUEST=.*$@REVERSE_PROXY_AUTH_REQUEST=/auth@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_CUSTOM_HOST=.*$@REVERSE_PROXY_CUSTOM_HOST=test.example.com@' /etc/bunkerweb/variables.env
            unset REVERSE_PROXY_WS
            unset REVERSE_PROXY_KEEPALIVE
            export REVERSE_PROXY_INTERCEPT_ERRORS="no"
            export REVERSE_PROXY_HEADERS="Test test;Test2 test2"
            export REVERSE_PROXY_HEADERS_CLIENT="Test test;Test2 test2"
            export REVERSE_PROXY_AUTH_REQUEST="/auth"
            export REVERSE_PROXY_CUSTOM_HOST="test.example.com"
        fi
    elif [ "$test" = "auth_signin" ] ; then
        echo "↪️ Running tests with reverseproxy activated and auth signin ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_INTERCEPT_ERRORS: "no"@REVERSE_PROXY_INTERCEPT_ERRORS: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_HEADERS: ".*"@REVERSE_PROXY_HEADERS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_HEADERS_CLIENT: ".*"@REVERSE_PROXY_HEADERS_CLIENT: ""@' {} \;
            sudo sed -i 's@REVERSE_PROXY_AUTH_REQUEST=.*$@REVERSE_PROXY_AUTH_REQUEST=/bad-auth@' /etc/bunkerweb/variables.env
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: ".*"@REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "http://reverseproxy-api:8080/auth"@' {} \;
        else
            sudo sed -i 's@REVERSE_PROXY_INTERCEPT_ERRORS=no$@REVERSE_PROXY_INTERCEPT_ERRORS=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_HEADERS=.*$@REVERSE_PROXY_HEADERS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_HEADERS_CLIENT=.*$@REVERSE_PROXY_HEADERS_CLIENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_AUTH_REQUEST=.*$@REVERSE_PROXY_AUTH_REQUEST=/bad-auth@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL=.*$@REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL=http://127.0.0.1:8080/auth@' /etc/bunkerweb/variables.env
            unset REVERSE_PROXY_INTERCEPT_ERRORS
            unset REVERSE_PROXY_HEADERS
            unset REVERSE_PROXY_HEADERS_CLIENT
            export REVERSE_PROXY_AUTH_REQUEST="/bad-auth"
            export REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL="http://127.0.0.1:8080/auth"
        fi
    fi

    if [ "$integration" == "linux" ]; then
        echo "↪️ Starting api ..."
        python3 api/main.py &
    fi

    echo "↪️ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "↪️ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "↪️ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "↪️ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "↪️ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("reverseproxy-bw-1" "reverseproxy-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "↪️ Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "↪️ Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "↪️ Linux stack is healthy ✅"
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
                echo "↪️ Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "↪️ ⚠ Linux stack got an issue, restarting ..."
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
            echo "↪️ Linux stack could not be healthy ❌"
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
        echo "↪️ Test \"$test\" failed ❌"
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
        echo "↪️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "↪️ Tests are done ! ✅"
