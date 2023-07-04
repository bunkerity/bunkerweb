#!/bin/bash

echo "📝 Building clientcache stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "📝 Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "📝 Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CLIENT_CACHE: "yes"@USE_CLIENT_CACHE: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_ETAG: "no"@CLIENT_CACHE_ETAG: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_CONTROL: "public, max-age=3600"@CLIENT_CACHE_CONTROL: "public, max-age=15552000"@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "📝 Cleaning up current stack ..."

    docker compose down -v --remove-orphans

    if [ $? -ne 0 ] ; then
        echo "📝 Down failed ❌"
        exit 1
    fi

    echo "📝 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "deactivated" "activated" "cache_extensions" "cache_etag" "cache_control"
do
    if [ "$test" = "deactivated" ] ; then
        echo "📝 Running tests without clientcache ..."
    elif [ "$test" = "activated" ] ; then
        echo "📝 Running tests with clientcache ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CLIENT_CACHE: "no"@USE_CLIENT_CACHE: "yes"@' {} \;
    elif [ "$test" = "cache_extensions" ] ; then
        echo "📝 Running tests when removing png from the cache extensions ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@' {} \;
    elif [ "$test" = "cache_etag" ] ; then
        echo "📝 Running tests when deactivating the etag ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_ETAG: "yes"@CLIENT_CACHE_ETAG: "no"@' {} \;
    elif [ "$test" = "cache_control" ] ; then
        echo "📝 Running tests whith clientcache control set to public, max-age=3600 ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_ETAG: "no"@CLIENT_CACHE_ETAG: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_CONTROL: "public, max-age=15552000"@CLIENT_CACHE_CONTROL: "public, max-age=3600"@' {} \;
    fi

    echo "📝 Starting stack ..."
    docker compose up -d
    if [ $? -ne 0 ] ; then
        echo "📝 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "📝 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "📝 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("clientcache-bw-1" "clientcache-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "📝 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "📝 Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests

    if [ $? -ne 0 ] ; then
        echo "📝 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "📝 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "📝 Tests are done ! ✅"
