#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🗃️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🗃️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🗃️ Building misc stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🗃️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "GENERATE_SELF_SIGNED_SSL=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_MODSECURITY=no" | sudo tee -a /etc/bunkerweb/variables.env

    echo "DISABLE_DEFAULT_SERVER=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIRECT_HTTP_TO_HTTPS=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "AUTO_REDIRECT_HTTP_TO_HTTPS=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "ALLOWED_METHODS=GET|POST|HEAD" | sudo tee -a /etc/bunkerweb/variables.env
    echo "MAX_CLIENT_SIZE=5m" | sudo tee -a /etc/bunkerweb/variables.env
    echo "SERVE_FILES=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "SSL_PROTOCOLS=TLSv1.2 TLSv1.3" | sudo tee -a /etc/bunkerweb/variables.env
    echo "HTTP2=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "LISTEN_HTTP=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "DENY_HTTP_STATUS=403" | sudo tee -a /etc/bunkerweb/variables.env
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
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_DEFAULT_SERVER: "yes"@DISABLE_DEFAULT_SERVER: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ALLOWED_METHODS: ".*"$@ALLOWED_METHODS: "GET|POST|HEAD"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@MAX_CLIENT_SIZE: "10m"@MAX_CLIENT_SIZE: "5m"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@SERVE_FILES: "no"@SERVE_FILES: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@SSL_PROTOCOLS: "TLSv1.2"@SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@HTTP2: "no"@HTTP2: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@LISTEN_HTTP: "no"@LISTEN_HTTP: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DENY_HTTP_STATUS: "444"@DENY_HTTP_STATUS: "403"@' {} \;
        else
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DISABLE_DEFAULT_SERVER=.*$@DISABLE_DEFAULT_SERVER=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@ALLOWED_METHODS=.*$@ALLOWED_METHODS=GET|POST|HEAD@' /etc/bunkerweb/variables.env
            sudo sed -i 's@MAX_CLIENT_SIZE=.*$@MAX_CLIENT_SIZE=5m@' /etc/bunkerweb/variables.env
            sudo sed -i 's@SERVE_FILES=.*$@SERVE_FILES=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@SSL_PROTOCOLS=.*$@SSL_PROTOCOLS=TLSv1.2 TLSv1.3@' /etc/bunkerweb/variables.env
            sudo sed -i 's@HTTP2=.*$@HTTP2=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@LISTEN_HTTP=.*$@LISTEN_HTTP=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DENY_HTTP_STATUS=.*$@DENY_HTTP_STATUS=403@' /etc/bunkerweb/variables.env
            unset GENERATE_SELF_SIGNED_SSL
            unset DISABLE_DEFAULT_SERVER
            unset ALLOWED_METHODS
            unset MAX_CLIENT_SIZE
            unset SERVE_FILES
            unset SSL_PROTOCOLS
            unset HTTP2
            unset LISTEN_HTTP
            unset DENY_HTTP_STATUS
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🗃️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🗃️ Cleanup failed ❌"
        exit 1
    fi

    echo "🗃️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "default" "ssl_generated" "tweaked" "deny_status_444" "TLSv1.2"
do
    if [ "$test" = "default" ] ; then
        echo "🗃️ Running tests when misc settings have default values except MAX_CLIENT_SIZE which have the value \"5m\" ..."
    elif [ "$test" = "ssl_generated" ] ; then
        echo "🗃️ Running tests when misc settings have default values and the ssl is generated in self signed ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
        else
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=yes@' /etc/bunkerweb/variables.env
            export GENERATE_SELF_SIGNED_SSL="yes"
        fi
    elif [ "$test" = "tweaked" ] ; then
        echo "🗃️ Running tests when misc settings have tweaked values ..."
        echo "ℹ️ Keeping the ssl generated in self signed ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_DEFAULT_SERVER: "no"@DISABLE_DEFAULT_SERVER: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ALLOWED_METHODS: ".*"$@ALLOWED_METHODS: "POST|HEAD"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@MAX_CLIENT_SIZE: "5m"@MAX_CLIENT_SIZE: "10m"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@SERVE_FILES: "yes"@SERVE_FILES: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@HTTP2: "yes"@HTTP2: "no"@' {} \;
        else
            sudo sed -i 's@DISABLE_DEFAULT_SERVER=.*$@DISABLE_DEFAULT_SERVER=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@ALLOWED_METHODS=.*$@ALLOWED_METHODS=POST|HEAD@' /etc/bunkerweb/variables.env
            sudo sed -i 's@MAX_CLIENT_SIZE=.*$@MAX_CLIENT_SIZE=10m@' /etc/bunkerweb/variables.env
            sudo sed -i 's@SERVE_FILES=.*$@SERVE_FILES=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@HTTP2=.*$@HTTP2=no@' /etc/bunkerweb/variables.env
            export DISABLE_DEFAULT_SERVER="yes"
            export ALLOWED_METHODS="POST|HEAD"
            export MAX_CLIENT_SIZE="10m"
            export SERVE_FILES="no"
            export HTTP2="no"
        fi
    elif [ "$test" = "deny_status_444" ] ; then
        echo "🗃️ Running tests when the server's deny status is set to 444 ..."
        echo "ℹ️ Keeping the ssl generated in self signed ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DENY_HTTP_STATUS: "403"@DENY_HTTP_STATUS: "444"@' {} \;
        else
            sudo sed -i 's@DENY_HTTP_STATUS=.*$@DENY_HTTP_STATUS=444@' /etc/bunkerweb/variables.env
            export DENY_HTTP_STATUS="444"
        fi
    elif [ "$test" = "TLSv1.2" ] ; then
        echo "🗃️ Running tests with only TLSv1.2 enabled and when the server is not listening on http ..."
        echo "ℹ️ Keeping the ssl generated in self signed ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_DEFAULT_SERVER: "yes"@DISABLE_DEFAULT_SERVER: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"@SSL_PROTOCOLS: "TLSv1.2"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@LISTEN_HTTP: "yes"@LISTEN_HTTP: "no"@' {} \;
        else
            sudo sed -i 's@DISABLE_DEFAULT_SERVER=.*$@DISABLE_DEFAULT_SERVER=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@SSL_PROTOCOLS=.*$@SSL_PROTOCOLS=TLSv1.2@' /etc/bunkerweb/variables.env
            sudo sed -i 's@LISTEN_HTTP=.*$@LISTEN_HTTP=no@' /etc/bunkerweb/variables.env
            export DISABLE_DEFAULT_SERVER="no"
            export SSL_PROTOCOLS="TLSv1.2"
            export LISTEN_HTTP="no"
        fi
    fi

    echo "🗃️ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🗃️ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🗃️ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🗃️ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🗃️ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("misc-bw-1" "misc-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🗃️ Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🗃️ Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🗃️ Linux stack is healthy ✅"
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
                echo "🗃️ Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🗃️ ⚠ Linux stack got an issue, restarting ..."
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
            echo "🗃️ Linux stack could not be healthy ❌"
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
        echo "🗃️ Test \"$test\" failed ❌"
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
        echo "🗃️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🗃️ Tests are done ! ✅"
