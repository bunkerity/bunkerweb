#!/bin/bash

echo "🔏 Building customcert stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🔏 Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🔏 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        rm -rf init/certs
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CUSTOM_SSL: "yes"@USE_CUSTOM_SSL: "no"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🔏 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🔏 Down failed ❌"
        exit 1
    fi

    echo "🔏 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🔏 Initializing workspace ..."
rm -rf init/certs
mkdir -p init/certs
docker compose -f docker-compose.init.yml up --build
if [ $? -ne 0 ] ; then
    echo "🔏 Build failed ❌"
    exit 1
elif ! [[ -f "init/certs/certificate.pem" ]]; then
    echo "🔏 certificate.pem not found ❌"
    exit 1
elif ! [[ -f "init/certs/privatekey.key" ]]; then
    echo "🔏 privatekey.key not found ❌"
    exit 1
fi

for test in "deactivated" "activated"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🔏 Running tests without the custom cert ..."
    elif [ "$test" = "activated" ] ; then
        echo "🔏 Running tests with the custom cert activated ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CUSTOM_SSL: "no"@USE_CUSTOM_SSL: "yes"@' {} \;
    fi

    echo "🔏 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🔏 Up failed ❌"
        exit 1
    fi

    # Check if stack is healthy
    echo "🔏 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("customcert-bw-1" "customcert-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🔏 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🔏 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🔏 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🔏 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🔏 Tests are done ! ✅"
