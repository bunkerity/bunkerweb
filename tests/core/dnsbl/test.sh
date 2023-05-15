#!/bin/bash

echo "🚫 Building dnsbl stack ..."

# Starting stack
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

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        rm -rf init/output
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_DNSBL: "no"@USE_DNSBL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DNSBL_LIST: ".*"@DNSBL_LIST: "bl.blocklist.de problems.dnsbl.sorbs.net"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ipv4_address: [0-9][0-9]*\.0@ipv4_address: 192.168@' {} \;
        sed -i 's@subnet: [0-9][0-9]*\.0@subnet: 192.168@' docker-compose.yml
        sed -i 's@www.example.com:[0-9][0-9]*\.0@www.example.com:192.168@' docker-compose.test.yml
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🚫 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🚫 Down failed ❌"
        exit 1
    fi

    echo "🚫 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🚫 Initializing workspace ..."
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
ip=${content[0]}
server=${content[1]}

echo "🚫 Will use IP: $ip"
echo "🚫 Will use DNSBL Server: $server"

for test in "activated" "deactivated" "list"
do
    if [ "$test" = "activated" ] ; then
        echo "🚫 Running tests with DNSBL activated and the server $server added to the list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DNSBL_LIST: ".*"@DNSBL_LIST: "bl.blocklist.de problems.dnsbl.sorbs.net '"$server"'"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ipv4_address: 192.168@ipv4_address: '"${ip%%.*}"'.0@' {} \;
        sed -i 's@subnet: 192.168@subnet: '"${ip%%.*}"'.0@' docker-compose.yml
        sed -i 's@www.example.com:192.168@www.example.com:'"${ip%%.*}"'.0@' docker-compose.test.yml
    elif [ "$test" = "deactivated" ] ; then
        echo "🚫 Running tests without DNSBL ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_DNSBL: "yes"@USE_DNSBL: "no"@' {} \;
    elif [ "$test" = "list" ] ; then
        echo "🚫 Running tests with DNSBL activated and without the server $server added to the list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_DNSBL: "no"@USE_DNSBL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DNSBL_LIST: ".*"@DNSBL_LIST: "bl.blocklist.de problems.dnsbl.sorbs.net"@' {} \;
    fi

    echo "🚫 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🚫 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        if [ $? -ne 0 ] ; then
            echo "🚫 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🚫 Waiting for stack to be healthy ..."
    i=0
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

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🚫 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
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
