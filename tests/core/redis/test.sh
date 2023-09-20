#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🧰 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🧰 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🧰 Building redis stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" = "docker" ] ; then
    docker compose pull bw-docker
    if [ $? -ne 0 ] ; then
        echo "🧰 Pull failed ❌"
        exit 1
    fi

    echo "🧰 Building custom redis image ..."
    docker compose build bw-redis
    if [ $? -ne 0 ] ; then
        echo "🧰 Build failed ❌"
        exit 1
    fi

    echo "🧰 Building tests images ..."
    docker compose -f docker-compose.test.yml build
    if [ $? -ne 0 ] ; then
        echo "🧰 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    sudo sed -i "/^USE_BLACKLIST=/d" /etc/bunkerweb/variables.env
    echo "BLACKLIST_IP_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "SESSIONS_NAME=test" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_REVERSE_SCAN=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_ANTIBOT=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_GREYLIST=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_IP=0.0.0.0/0" | sudo tee -a /etc/bunkerweb/variables.env
    echo "WHITELIST_COUNTRY=AU" | sudo tee -a /etc/bunkerweb/variables.env

    echo "🧰 Installing Redis ..."
    sudo apt install --no-install-recommends -y redis
    redis-server --daemonize yes
    if [ $? -ne 0 ] ; then
        echo "🧰 Redis start failed ❌"
        exit 1
    fi
    echo "🧰 Redis installed ✅"

    echo "🧰 Generating redis certs ..."
    mkdir tls
    openssl genrsa -out tls/ca.key 4096
    openssl req \
        -x509 -new -nodes -sha256 \
        -key tls/ca.key \
        -days 365 \
        -subj /CN=bw-redis/ \
        -out tls/ca.crt
    openssl req \
        -x509 -nodes -newkey rsa:4096 \
        -keyout tls/redis.key \
        -out tls/redis.pem \
        -days 365 \
        -subj /CN=bw-redis/
    sudo chmod -R 640 tls
    echo "🧰 Certs generated ✅"

    echo "USE_REDIS=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_HOST=127.0.0.1" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_PORT=6379" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_DATABASE=0" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_SSL=no" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_SCAN: "yes"@USE_REVERSE_SCAN: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_ANTIBOT: "cookie"@USE_ANTIBOT: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "1"@REDIS_DATABASE: "0"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "yes"@REDIS_SSL: "no"@' {} \;
        else
            sudo rm -rf tls
            sudo sed -i 's@USE_REVERSE_SCAN=.*$@USE_REVERSE_SCAN=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@USE_ANTIBOT=.*$@USE_ANTIBOT=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_PORT=.*$@REDIS_PORT=6379@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_DATABASE=.*$@REDIS_DATABASE=0@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_SSL=.*$@REDIS_SSL=no@' /etc/bunkerweb/variables.env
            unset USE_REVERSE_SCAN
            unset USE_ANTIBOT
            unset REDIS_PORT
            unset REDIS_DATABASE
            unset REDIS_SSL
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🧰 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    if [ $? -ne 0 ] ; then
        echo "🧰 Cleanup failed ❌"
        exit 1
    fi

    echo "🧰 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "activated" "reverse_scan" "antibot" "tweaked"
do
    if [ "$test" = "activated" ] ; then
        echo "🧰 Running tests with redis with default values ..."
    elif [ "$test" = "reverse_scan" ] ; then
        echo "🧰 Running tests with redis with reverse scan activated ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_SCAN: "no"@USE_REVERSE_SCAN: "yes"@' {} \;
        else
            sudo sed -i 's@USE_REVERSE_SCAN=.*$@USE_REVERSE_SCAN=yes@' /etc/bunkerweb/variables.env
            export USE_REVERSE_SCAN="yes"
        fi
    elif [ "$test" = "antibot" ] ; then
        echo "🧰 Running tests with redis with antibot cookie activated ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_REVERSE_SCAN: "yes"@USE_REVERSE_SCAN: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_ANTIBOT: "no"@USE_ANTIBOT: "cookie"@' {} \;
        else
            sudo sed -i 's@USE_REVERSE_SCAN=.*$@USE_REVERSE_SCAN=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@USE_ANTIBOT=.*$@USE_ANTIBOT=cookie@' /etc/bunkerweb/variables.env
            export USE_REVERSE_SCAN="no"
            export USE_ANTIBOT="cookie"
        fi
    elif [ "$test" = "tweaked" ] ; then
        echo "🧰 Running tests with redis' settings tweaked ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_ANTIBOT: "cookie"@USE_ANTIBOT: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6380"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "0"@REDIS_DATABASE: "1"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "no"@REDIS_SSL: "yes"@' {} \;
        else
            sudo sed -i 's@USE_ANTIBOT=.*$@USE_ANTIBOT=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_PORT=.*$@REDIS_PORT=6380@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_DATABASE=.*$@REDIS_DATABASE=1@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_SSL=.*$@REDIS_SSL=yes@' /etc/bunkerweb/variables.env
            unset USE_ANTIBOT
            unset REDIS_PORT
            unset REDIS_DATABASE
            unset REDIS_SSL

            echo "🧰 Stoping redis ..."
            redis-cli shutdown
            if [ $? -ne 0 ] ; then
                echo "🧰 Redis stop failed ❌"
                exit 1
            fi
            echo "🧰 Redis stopped ✅"
            echo "🧰 Starting redis with tweaked settings ..."
            redis-server --tls-port 6380 --port 0 --tls-cert-file tls/redis.pem --tls-key-file tls/redis.key --tls-ca-cert-file tls/ca.crt --tls-auth-clients no --daemonize yes
            if [ $? -ne 0 ] ; then
                echo "🧰 Redis start failed ❌"
                exit 1
            fi
            echo "🧰 Redis started ✅"
        fi
    fi

    echo "🧰 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🧰 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            if [ $? -ne 0 ] ; then
                echo "🧰 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        if [ $? -ne 0 ] ; then
            echo "🧰 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🧰 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("redis-bw-1" "redis-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🧰 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🧰 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        while [ $i -lt 120 ] ; do
            check="$(sudo cat /var/log/bunkerweb/error.log | grep "BunkerWeb is ready")"
            if ! [ -z "$check" ] ; then
                echo "🧰 Linux stack is healthy ✅"
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
            echo "🧰 Linux stack is not healthy ❌"
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
        echo "🧰 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        if [ "$integration" == "docker" ] ; then
            docker compose logs bw bw-scheduler
        else
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
            echo "🛡️ Showing Geckodriver logs ..."
            sudo cat geckodriver.log
        fi
        exit 1
    else
        echo "🧰 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🧰 Tests are done ! ✅"
