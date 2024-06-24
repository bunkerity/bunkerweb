#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🌍 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🌍 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🌍 Building country stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🌍 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "USE_REAL_IP=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REAL_IP_FROM=127.0.0.0/24" | sudo tee -a /etc/bunkerweb/variables.env

    echo "BLACKLIST_COUNTRY=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "WHITELIST_COUNTRY=" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export COUNTRY=""
    export TEST_TYPE="linux"
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_COUNTRY: "US"@BLACKLIST_COUNTRY: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_COUNTRY: "GB"@WHITELIST_COUNTRY: ""@' {} \;
        else
            sudo sed -i 's@BLACKLIST_COUNTRY=.*$@BLACKLIST_COUNTRY=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@WHITELIST_COUNTRY=.*$@WHITELIST_COUNTRY=@' /etc/bunkerweb/variables.env
            unset BLACKLIST_COUNTRY
            unset WHITELIST_COUNTRY
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🌍 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🌍 Cleanup failed ❌"
        exit 1
    fi

    echo "🌍 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "deactivated" "blacklist" "whitelist"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🌍 Running tests without the country plugin ..."
    elif [ "$test" = "blacklist" ] ; then
        echo "🌍 Running tests when blacklisting United States ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_COUNTRY: ""@BLACKLIST_COUNTRY: "US"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_COUNTRY=.*$@BLACKLIST_COUNTRY=US@' /etc/bunkerweb/variables.env
            export BLACKLIST_COUNTRY="US"
        fi
    elif [ "$test" = "whitelist" ] ; then
        echo "🌍 Running tests when whitelisting England ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_COUNTRY: "US"@BLACKLIST_COUNTRY: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_COUNTRY: ""@WHITELIST_COUNTRY: "GB"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_COUNTRY=.*$@BLACKLIST_COUNTRY=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@WHITELIST_COUNTRY=.*$@WHITELIST_COUNTRY=GB@' /etc/bunkerweb/variables.env
            unset BLACKLIST_COUNTRY
            export WHITELIST_COUNTRY="GB"
        fi
    fi

    echo "🌍 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🌍 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🌍 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🌍 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🌍 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("country-bw-1" "country-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🌍 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🌍 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🌍 Linux stack is healthy ✅"
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
                echo "🌍 Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🌍 ⚠ Linux stack got an issue, restarting ..."
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
            echo "🌍 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests

    echo "🌍 Starting the GB country"
    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up tests-gb --abort-on-container-exit --exit-code-from tests-gb
    else
        export COUNTRY="GB"
        python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🌍 Test \"$test\" failed for the GB country ❌"
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
        echo "🌍 Test \"$test\" succeeded for the GB country ✅"
    fi

    echo "🌍 Starting the GB country"
    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up tests-us --abort-on-container-exit --exit-code-from tests-us
    else
        export COUNTRY="GB"
        python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🌍 Test \"$test\" failed for the GB country ❌"
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
        echo "🌍 Test \"$test\" succeeded for the GB country ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🌍 Tests are done ! ✅"
