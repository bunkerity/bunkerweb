#!/bin/bash

echo "🔑 Building selfsigned stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🔑 Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🔑 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SELF_SIGNED_SSL_EXPIRY: "30"@SELF_SIGNED_SSL_EXPIRY: "365"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SELF_SIGNED_SSL_SUBJ: "/CN=example.com/"@SELF_SIGNED_SSL_SUBJ: "/CN=www.example.com/"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🔑 Cleaning up current stack ..."

    docker compose down -v --remove-orphans

    if [ $? -ne 0 ] ; then
        echo "🔑 Down failed ❌"
        exit 1
    fi

    echo "🔑 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "deactivated" "activated" "tweaked_options"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🔑 Running tests without selfsigned ..."
    elif [ "$test" = "activated" ] ; then
        echo "🔑 Running tests with selfsigned activated ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
    elif [ "$test" = "tweaked_options" ] ; then
        echo "🔑 Running tests with selfsigned's options tweaked ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SELF_SIGNED_SSL_EXPIRY: "365"@SELF_SIGNED_SSL_EXPIRY: "30"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SELF_SIGNED_SSL_SUBJ: "/CN=www.example.com/"@SELF_SIGNED_SSL_SUBJ: "/CN=example.com/"@' {} \;
    fi

    echo "🔑 Starting stack ..."
    docker compose up -d
    if [ $? -ne 0 ] ; then
        echo "🔑 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🔑 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🔑 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("selfsigned-bw-1" "selfsigned-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🔑 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🔑 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

    if [ $? -ne 0 ] ; then
        echo "🔑 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🔑 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🔑 Tests are done ! ✅"
