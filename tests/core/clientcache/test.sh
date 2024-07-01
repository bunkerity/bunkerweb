#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "📝 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "📝 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "📝 Building clientcache stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📝 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "USE_CLIENT_CACHE=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CLIENT_CACHE_EXTENSIONS=jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CLIENT_CACHE_ETAG=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CLIENT_CACHE_CONTROL=public, max-age=15552000" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    sudo cp image.png /var/www/html/image.png
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CLIENT_CACHE: "yes"@USE_CLIENT_CACHE: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_ETAG: "no"@CLIENT_CACHE_ETAG: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_CONTROL: "public, max-age=3600"@CLIENT_CACHE_CONTROL: "public, max-age=15552000"@' {} \;
        else
            sudo sed -i 's@USE_CLIENT_CACHE=.*$@USE_CLIENT_CACHE=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CLIENT_CACHE_EXTENSIONS=.*$@CLIENT_CACHE_EXTENSIONS=jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CLIENT_CACHE_ETAG=.*$@CLIENT_CACHE_ETAG=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CLIENT_CACHE_CONTROL=.*$@CLIENT_CACHE_CONTROL=public, max-age=15552000@' /etc/bunkerweb/variables.env
            unset USE_CLIENT_CACHE
            unset CLIENT_CACHE_EXTENSIONS
            unset CLIENT_CACHE_ETAG
            unset CLIENT_CACHE_CONTROL
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "📝 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📝 Cleanup failed ❌"
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
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_CLIENT_CACHE: "no"@USE_CLIENT_CACHE: "yes"@' {} \;
        else
            sudo sed -i 's@USE_CLIENT_CACHE=.*$@USE_CLIENT_CACHE=yes@' /etc/bunkerweb/variables.env
            export USE_CLIENT_CACHE="yes"
        fi
    elif [ "$test" = "cache_extensions" ] ; then
        echo "📝 Running tests when removing png from the cache extensions ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@' {} \;
        else
            sudo sed -i 's@CLIENT_CACHE_EXTENSIONS=.*$@CLIENT_CACHE_EXTENSIONS=jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2@' /etc/bunkerweb/variables.env
            export CLIENT_CACHE_EXTENSIONS="jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"
        fi
    elif [ "$test" = "cache_etag" ] ; then
        echo "📝 Running tests when deactivating the etag ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_ETAG: "yes"@CLIENT_CACHE_ETAG: "no"@' {} \;
        else
            sudo sed -i 's@CLIENT_CACHE_EXTENSIONS=.*$@CLIENT_CACHE_EXTENSIONS=jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CLIENT_CACHE_ETAG=.*$@CLIENT_CACHE_ETAG=no@' /etc/bunkerweb/variables.env
            export CLIENT_CACHE_EXTENSIONS="jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"
            export CLIENT_CACHE_ETAG="no"
        fi
    elif [ "$test" = "cache_control" ] ; then
        echo "📝 Running tests with clientcache control set to public, max-age=3600 ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_ETAG: "no"@CLIENT_CACHE_ETAG: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CLIENT_CACHE_CONTROL: "public, max-age=15552000"@CLIENT_CACHE_CONTROL: "public, max-age=3600"@' {} \;
        else
            sudo sed -i 's@CLIENT_CACHE_ETAG=.*$@CLIENT_CACHE_ETAG=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CLIENT_CACHE_CONTROL=.*$@CLIENT_CACHE_CONTROL=public, max-age=3600@' /etc/bunkerweb/variables.env
            export CLIENT_CACHE_ETAG="yes"
            export CLIENT_CACHE_CONTROL="public, max-age=3600"
        fi
    fi

    echo "📝 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "📝 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "📝 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "📝 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "📝 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("clientcache-bw-1" "clientcache-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
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
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "📝 Linux stack is healthy ✅"
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
                echo "📝 Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "📝 ⚠ Linux stack got an issue, restarting ..."
                sudo journalctl --rotate
                sudo journalctl --vacuum-time=1s
                manual=1
                cleanup_stack
                manual=0
                sudo systemctl start bunkerweb
                retries=$((retries+1))
            else
                healthy="true"
            fi
        done
        if [ "$retries" -ge 5 ] ; then
            echo "📝 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests

    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
    else
        python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "📝 Test \"$test\" failed ❌"
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
        echo "📝 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "📝 Tests are done ! ✅"
