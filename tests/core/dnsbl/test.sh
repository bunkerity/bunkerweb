#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🚫 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🚫 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🚫 Building dnsbl stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" = "docker" ] ; then
    docker compose pull bw-docker
    if [ $? -ne 0 ] ; then
        echo "🚫 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    if [ $? -ne 0 ] ; then
        echo "🚫 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "USE_REAL_IP=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REAL_IP_FROM=127.0.0.0/24" | sudo tee -a /etc/bunkerweb/variables.env

    echo "USE_DNSBL=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "DNSBL_LIST=bl.blocklist.de problems.dnsbl.sorbs.net" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            rm -rf init/output
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_DNSBL: "no"@USE_DNSBL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DNSBL_LIST: ".*"@DNSBL_LIST: "bl.blocklist.de problems.dnsbl.sorbs.net"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ipv4_address: [0-9][0-9]*\.0@ipv4_address: 192.168@' {} \;
            sed -i 's@subnet: [0-9][0-9]*\.0@subnet: 192.168@' docker-compose.yml
            sed -i 's@www.example.com:[0-9][0-9]*\.0@www.example.com:192.168@' docker-compose.test.yml
        else
            sudo sed -i 's@USE_DNSBL=.*$@USE_DNSBL=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DNSBL_LIST=.*$@DNSBL_LIST=bl.blocklist.de problems.dnsbl.sorbs.net@' /etc/bunkerweb/variables.env
            unset USE_DNSBL
            unset DNSBL_LIST
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🚫 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    if [ $? -ne 0 ] ; then
        echo "🚫 Cleanup failed ❌"
        exit 1
    fi

    echo "🚫 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🚫 Initializing workspace ..."
if [ "$integration" = "docker" ] ; then
    rm -rf init/output
    mkdir -p init/output
    docker compose -f docker-compose.init.yml up --build
    if [ $? -ne 0 ] ; then
        echo "🚫 Build failed ❌"
        exit 1
    elif ! [[ -f "init/output/dnsbl_ip.txt" ]] ; then
        echo "🚫 Initialization failed, dnsbl_ip.txt not found ❌"
        exit 1
    fi

    content=($(cat init/output/dnsbl_ip.txt))
else
    python3 init/main.py
    if [ $? -ne 0 ] ; then
        echo "🚫 Initialization failed ❌"
        exit 1
    elif ! [[ -f "dnsbl_ip.txt" ]] ; then
        echo "🚫 Initialization failed, dnsbl_ip.txt not found ❌"
        exit 1
    fi

    content=($(cat dnsbl_ip.txt))
fi

ip=${content[0]}
server=${content[1]}

echo "🚫 Will use IP: $ip"
echo "🚫 Will use DNSBL Server: $server"

for test in "activated" "deactivated" "list"
do
    if [ "$test" = "activated" ] ; then
        echo "🚫 Running tests with DNSBL activated and the server $server added to the list ..."
        if [ "$integration" = "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DNSBL_LIST: ".*"@DNSBL_LIST: "bl.blocklist.de problems.dnsbl.sorbs.net '"$server"'"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@ipv4_address: 192.168@ipv4_address: '"${ip%%.*}"'.0@' {} \;
            sed -i 's@subnet: 192.168@subnet: '"${ip%%.*}"'.0@' docker-compose.yml
            sed -i 's@www.example.com:192.168@www.example.com:'"${ip%%.*}"'.0@' docker-compose.test.yml
        else
            sudo sed -i 's@DNSBL_LIST=.*$@DNSBL_LIST=bl.blocklist.de problems.dnsbl.sorbs.net '"$server"'@' /etc/bunkerweb/variables.env
            export DNSBL_LIST="bl.blocklist.de problems.dnsbl.sorbs.net $server"
            export IP_ADDRESS="$ip"
        fi
    elif [ "$test" = "deactivated" ] ; then
        echo "🚫 Running tests without DNSBL ..."
        if [ "$integration" = "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_DNSBL: "yes"@USE_DNSBL: "no"@' {} \;
        else
            sudo sed -i 's@USE_DNSBL=.*$@USE_DNSBL=no@' /etc/bunkerweb/variables.env
            export USE_DNSBL="no"
        fi
    elif [ "$test" = "list" ] ; then
        echo "🚫 Running tests with DNSBL activated and without the server $server added to the list ..."
        if [ "$integration" = "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_DNSBL: "no"@USE_DNSBL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DNSBL_LIST: ".*"@DNSBL_LIST: "bl.blocklist.de problems.dnsbl.sorbs.net"@' {} \;
        else
            sudo sed -i 's@USE_DNSBL=.*$@USE_DNSBL=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DNSBL_LIST=.*$@DNSBL_LIST=bl.blocklist.de problems.dnsbl.sorbs.net@' /etc/bunkerweb/variables.env
            unset USE_DNSBL
            unset DNSBL_LIST
        fi
    fi

    echo "🚫 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🚫 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            if [ $? -ne 0 ] ; then
                echo "🚫 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        if [ $? -ne 0 ] ; then
            echo "🚫 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🚫 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("dnsbl-bw-1" "dnsbl-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🚫 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🚫 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                check="$(sudo cat /var/log/bunkerweb/error.log | grep "BunkerWeb is ready")"
                if ! [ -z "$check" ] ; then
                    echo "🚫 Linux stack is healthy ✅"
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
                echo "🚫 Linux stack is not healthy ❌"
                exit 1
            fi

            check="$(sudo cat /var/log/bunkerweb/error.log | grep "SYSTEMCTL - ❌")"
            if ! [ -z "$check" ] ; then
                echo "🚫 ⚠ Linux stack got an issue, restarting ..."
                sudo systemctl stop bunkerweb
                sudo systemctl start bunkerweb
                retries=$((retries+1))
            else
                healthy="true"
            fi
        done
        if [ $retries -ge 5 ] ; then
            echo "🚫 Linux stack could not be healthy ❌"
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
        echo "🚫 Test \"$test\" failed ❌"
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
        echo "🚫 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🚫 Tests are done ! ✅"
