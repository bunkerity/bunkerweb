#!/bin/bash

echo "🛰️ Building cors stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🛰️ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🛰️ Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CORS: "yes"@USE_CORS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: "http://www.example.com"@CORS_ALLOW_ORIGIN: "\*"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "X-Test"@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "3600"@CORS_MAX_AGE: "86400"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "yes"@CORS_ALLOW_CREDENTIALS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_HEADERS: "X-Test"@CORS_ALLOW_HEADERS: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🛰️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🛰️ Down failed ❌"
        exit 1
    fi

    echo "🛰️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "deactivated" "activated" "allow_origin" "expose_headers" "max_age" "allow_credentials" "allow_methods" "allow_headers"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🛰️ Running tests without cors ..."
    elif [ "$test" = "activated" ] ; then
        echo "🛰️ Running tests with cors ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CORS: "no"@USE_CORS: "yes"@' {} \;
    elif [ "$test" = "allow_origin" ] ; then
        echo "🛰️ Running tests with cors allow origin set to http://www.example.com ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: "\*"@CORS_ALLOW_ORIGIN: "http://www.example.com"@' {} \;
    elif [ "$test" = "expose_headers" ] ; then
        echo "🛰️ Running tests with cors expose headers set to X-Test ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_ORIGIN: "http://www.example.com"@CORS_ALLOW_ORIGIN: "\*"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@CORS_EXPOSE_HEADERS: "X-Test"@' {} \;
    elif [ "$test" = "max_age" ] ; then
        echo "🛰️ Running tests with cors max age set to 3600 ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_EXPOSE_HEADERS: "X-Test"@CORS_EXPOSE_HEADERS: "Content-Length,Content-Range"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "86400"@CORS_MAX_AGE: "3600"@' {} \;
    elif [ "$test" = "allow_credentials" ] ; then
        echo "🛰️ Running tests with cors allow credentials is set to yes ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_MAX_AGE: "3600"@CORS_MAX_AGE: "86400"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "no"@CORS_ALLOW_CREDENTIALS: "yes"@' {} \;
    elif [ "$test" = "allow_methods" ] ; then
        echo "🛰️ Running tests with cors allow methods is set to GET, HEAD, POST, OPTIONS ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_CREDENTIALS: "yes"@CORS_ALLOW_CREDENTIALS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@' {} \;
    elif [ "$test" = "allow_headers" ] ; then
        echo "🛰️ Running tests with cors allow headers is set to X-Test ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_METHODS: "GET, HEAD, POST, OPTIONS"@CORS_ALLOW_METHODS: "GET, POST, OPTIONS"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CORS_ALLOW_HEADERS: "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"@CORS_ALLOW_HEADERS: "X-Test"@' {} \;
    fi

    echo "🛰️ Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🛰️ Up failed ❌"
        exit 1
    fi

    # Check if stack is healthy
    echo "🛰️ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("cors-bw-1" "cors-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🛰️ Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🛰️ Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🛰️ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🛰️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🛰️ Tests are done ! ✅"
