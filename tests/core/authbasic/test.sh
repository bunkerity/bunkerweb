#!/bin/bash

echo "🔐 Building authbasic stack ..."

# Starting stack
docker compose pull bw-docker app1
if [ $? -ne 0 ] ; then
    echo "🔐 Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🔐 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_AUTH_BASIC: "yes"@USE_AUTH_BASIC: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_LOCATION: "/auth"@AUTH_BASIC_LOCATION: "sitewide"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_USER: "admin"@AUTH_BASIC_USER: "bunkerity"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_PASSWORD: "password"@AUTH_BASIC_PASSWORD: "Secr3tP\@ssw0rd"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🔐 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🔐 Down failed ❌"
        exit 1
    fi

    echo "🔐 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "deactivated" "sitewide" "location" "user" "password"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🔐 Running tests without authbasic ..."
    elif [ "$test" = "sitewide" ] ; then
        echo "🔐 Running tests with sitewide authbasic ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_AUTH_BASIC: "no"@USE_AUTH_BASIC: "yes"@' {} \;
    elif [ "$test" = "location" ] ; then
        echo "🔐 Running tests with the location changed ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_LOCATION: "sitewide"@AUTH_BASIC_LOCATION: "/auth"@' {} \;
    elif [ "$test" = "user" ] ; then
        echo "🔐 Running tests with the user changed ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_LOCATION: "/auth"@AUTH_BASIC_LOCATION: "sitewide"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_USER: "bunkerity"@AUTH_BASIC_USER: "admin"@' {} \;
    elif [ "$test" = "password" ] ; then
        echo "🔐 Running tests with the password changed ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@AUTH_BASIC_PASSWORD: "Secr3tP\@ssw0rd"@AUTH_BASIC_PASSWORD: "password"@' {} \;
    fi

    echo "🔐 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🔐 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "🔐 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🔐 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("authbasic-bw-1" "authbasic-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🔐 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🔐 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

    if [ $? -ne 0 ] ; then
        echo "🔐 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🔐 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🔐 Tests are done ! ✅"
