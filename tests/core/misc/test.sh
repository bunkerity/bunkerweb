#!/bin/bash

echo "🗃️ Building misc stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🗃️ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🗃️ Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_DEFAULT_SERVER: "yes"@DISABLE_DEFAULT_SERVER: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ALLOWED_METHODS: ".*"$@ALLOWED_METHODS: "GET|POST|HEAD"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@MAX_CLIENT_SIZE: "10m"@MAX_CLIENT_SIZE: "5m"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SERVE_FILES: "no"@SERVE_FILES: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SSL_PROTOCOLS: "TLSv1.2"@SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@HTTP2: "no"@HTTP2: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@LISTEN_HTTP: "no"@LISTEN_HTTP: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DENY_HTTP_STATUS: "444"@DENY_HTTP_STATUS: "403"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🗃️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🗃️ Down failed ❌"
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
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
    elif [ "$test" = "tweaked" ] ; then
        echo "🗃️ Running tests when misc settings have tweaked values ..."
        echo "ℹ️ Keeping the ssl generated in self signed ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_DEFAULT_SERVER: "no"@DISABLE_DEFAULT_SERVER: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@ALLOWED_METHODS: ".*"$@ALLOWED_METHODS: "POST|HEAD"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@MAX_CLIENT_SIZE: "5m"@MAX_CLIENT_SIZE: "10m"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SERVE_FILES: "yes"@SERVE_FILES: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@HTTP2: "yes"@HTTP2: "no"@' {} \;
    elif [ "$test" = "deny_status_444" ] ; then
        echo "🗃️ Running tests when the server's deny status is set to 444 ..."
        echo "ℹ️ Keeping the ssl generated in self signed ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DENY_HTTP_STATUS: "403"@DENY_HTTP_STATUS: "444"@' {} \;
    elif [ "$test" = "TLSv1.2" ] ; then
        echo "🗃️ Running tests with only TLSv1.2 enabled and when the server is not listening on http ..."
        echo "ℹ️ Keeping the ssl generated in self signed ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_DEFAULT_SERVER: "yes"@DISABLE_DEFAULT_SERVER: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"@SSL_PROTOCOLS: "TLSv1.2"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@LISTEN_HTTP: "yes"@LISTEN_HTTP: "no"@' {} \;
    fi

    echo "🗃️ Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🗃️ Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "🗃️ Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🗃️ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("misc-bw-1" "misc-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
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

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🗃️ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
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
