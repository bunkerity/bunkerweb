#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "👮 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "👮 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "👮 Building modsecurity stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" = "docker" ] ; then
    docker compose pull bw-docker
    if [ $? -ne 0 ] ; then
        echo "👮 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    if [ $? -ne 0 ] ; then
        echo "👮 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "USE_MODSECURITY=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_MODSECURITY_CRS=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "MODSECURITY_SEC_AUDIT_ENGINE=RelevantOnly" | sudo tee -a /etc/bunkerweb/variables.env
    echo "MODSECURITY_SEC_RULE_ENGINE=On" | sudo tee -a /etc/bunkerweb/variables.env
    echo "MODSECURITY_SEC_AUDIT_LOG_PARTS=ABCFHZ" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY: "no"@USE_MODSECURITY: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY_CRS: "no"@USE_MODSECURITY_CRS: "yes"@' {} \;
        else
            sudo sed -i 's@USE_MODSECURITY=.*$@USE_MODSECURITY=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@USE_MODSECURITY_CRS=.*$@USE_MODSECURITY_CRS=yes@' /etc/bunkerweb/variables.env
            unset USE_MODSECURITY
            unset USE_MODSECURITY_CRS
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "👮 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    if [ $? -ne 0 ] ; then
        echo "👮 Cleanup failed ❌"
        exit 1
    fi

    echo "👮 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "activated" "crs_deactivated" "deactivated"
do
    if [ "$test" = "activated" ] ; then
        echo "👮 Running tests with modsecurity activated ..."
    elif [ "$test" = "crs_deactivated" ] ; then
        echo "👮 Running tests without the CRS ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY_CRS: "yes"@USE_MODSECURITY_CRS: "no"@' {} \;
        else
            sudo sed -i 's@USE_MODSECURITY_CRS=.*$@USE_MODSECURITY_CRS=no@' /etc/bunkerweb/variables.env
            export USE_MODSECURITY_CRS="no"
        fi
    elif [ "$test" = "deactivated" ] ; then
        echo "👮 Running tests without modsecurity ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY_CRS: "no"@USE_MODSECURITY_CRS: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_MODSECURITY: "yes"@USE_MODSECURITY: "no"@' {} \;
        else
            sudo sed -i 's@USE_MODSECURITY_CRS=.*$@USE_MODSECURITY_CRS=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@USE_MODSECURITY=.*$@USE_MODSECURITY=no@' /etc/bunkerweb/variables.env
            unset USE_MODSECURITY_CRS
            export USE_MODSECURITY="no"
        fi
    fi

    echo "👮 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "👮 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            if [ $? -ne 0 ] ; then
                echo "👮 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        if [ $? -ne 0 ] ; then
            echo "👮 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "👮 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("modsecurity-bw-1" "modsecurity-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "👮 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "👮 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                check="$(sudo cat /var/log/bunkerweb/error.log | grep "BunkerWeb is ready")"
                if ! [ -z "$check" ] ; then
                    echo "👮 Linux stack is healthy ✅"
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
                echo "👮 Linux stack is not healthy ❌"
                exit 1
            fi

            check="$(sudo cat /var/log/bunkerweb/error.log | grep "SYSTEMCTL - ❌")"
            if ! [ -z "$check" ] ; then
                echo "👮 ⚠ Linux stack got an issue, restarting ..."
                sudo systemctl stop bunkerweb
                sudo systemctl start bunkerweb
                retries=$((retries+1))
            else
                healthy="true"
            fi
        done
        if [ $retries -ge 5 ] ; then
            echo "👮 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests

    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
    else
        python3 main.py
    fi

    if [ $? -ne 0 ] ; then
        echo "👮 Test \"$test\" failed ❌"
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
        echo "👮 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "👮 Tests are done ! ✅"
