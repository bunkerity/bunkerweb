#!/bin/bash

echo "🎚️ Building limit stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🎚️ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🎚️ Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_REQ: "yes"@USE_LIMIT_REQ: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@LIMIT_REQ_URL: ".*"$@LIMIT_REQ_URL: "/"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@LIMIT_REQ_RATE: ".*"$@LIMIT_REQ_RATE: "2r/s"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_CONN: "no"@USE_LIMIT_CONN: "yes"@' {} \;

        if [[ $(sed '22!d' docker-compose.yml) = '      LIMIT_REQ_URL_1: "/custom"' ]] ; then
            sed -i '22d' docker-compose.yml
        fi

        if [[ $(sed '22!d' docker-compose.yml) = '      LIMIT_REQ_RATE_1: "4r/s"' ]] ; then
            sed -i '22d' docker-compose.yml
        fi

        if [[ $(sed '11!d' docker-compose.test.yml) = '      LIMIT_REQ_URL_1: "/custom"' ]] ; then
            sed -i '11d' docker-compose.test.yml
        fi

        if [[ $(sed '11!d' docker-compose.test.yml) = '      LIMIT_REQ_RATE_1: "4r/s"' ]] ; then
            sed -i '11d' docker-compose.test.yml
        fi

        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🎚️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🎚️ Down failed ❌"
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
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_CONN: "yes"@USE_LIMIT_CONN: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_REQ: "no"@USE_LIMIT_REQ: "yes"@' {} \;
    elif [ "$test" = "augmented" ] ; then
        echo "🎚️ Running tests with limit req rate set to 10r/s ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@LIMIT_REQ_RATE: ".*"$@LIMIT_REQ_RATE: "10r/s"@' {} \;
    elif [ "$test" = "custom_endpoint_rate" ] ; then
        echo "🎚️ Running tests with a custom endpoint rate ..."
        sed -i '22i \      LIMIT_REQ_URL_1: "/custom"' docker-compose.yml
        sed -i '23i \      LIMIT_REQ_RATE_1: "4r/s"' docker-compose.yml
        sed -i '11i \      LIMIT_REQ_URL_1: "/custom"' docker-compose.test.yml
        sed -i '12i \      LIMIT_REQ_RATE_1: "4r/s"' docker-compose.test.yml
    elif [ "$test" = "deactivated_req" ] ; then
        echo "🎚️ Running tests without limit req ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_LIMIT_REQ: "yes"@USE_LIMIT_REQ: "no"@' {} \;
    fi

    echo "🎚️ Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🎚️ Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        if [ $? -ne 0 ] ; then
            echo "🎚️ Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🎚️ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("limit-bw-1" "limit-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
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

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🎚️ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
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
