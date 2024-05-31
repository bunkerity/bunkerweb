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

echo "🧰 Generating redis certs ..."
sudo rm -rf tls
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

openssl genrsa -out tls/sentinel_ca.key 4096
openssl req \
    -x509 -new -nodes -sha256 \
    -key tls/sentinel_ca.key \
    -days 365 \
    -subj /CN=bw-redis-sentinel/ \
    -out tls/sentinel_ca.crt

openssl req \
    -x509 -nodes -newkey rsa:4096 \
    -keyout tls/sentinel.key \
    -out tls/sentinel.pem \
    -days 365 \
    -subj /CN=bw-redis-sentinel/

sudo chmod -R 777 tls
echo "🧰 Certs generated ✅"

echo "🧰 Generating redis acl files ..."
sudo rm -rf acl
mkdir acl

# Starting stack
if [ "$integration" == "docker" ] ; then
    echo "user default on nopass +@all ~* &* +@all -@all +@all" > acl/redis.acl
    echo "user bunkerweb on >secret +@all ~* +@all -@all +@all" >> acl/redis.acl
    echo "user default on nopass +@all ~* &* +@all -@all +@all" > acl/sentinel.acl
    echo "user bunkerweb_sentinel on >sentinel_secret +@all ~* +@all -@all +@all" >> acl/sentinel.acl
    sudo chmod -R 777 acl
    echo "🧰 Redis acl files generated ✅"

    docker compose pull bw-docker
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🧰 Pull failed ❌"
        exit 1
    fi

    echo "🧰 Building custom redis image ..."
    docker compose build bw-redis
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🧰 Build failed ❌"
        exit 1
    fi

    echo "🧰 Building tests images ..."
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🧰 Build failed ❌"
        exit 1
    fi
else
    echo "user default on nopass +@all ~* +@all -@all +@all" > acl/redis.acl
    echo "user bunkerweb on >secret +@all ~* +@all -@all +@all" >> acl/redis.acl
    sudo chmod -R 777 acl
    echo "🧰 Redis acl files generated ✅"

    sudo systemctl stop bunkerweb
    sudo sed -i "/^USE_BLACKLIST=/d" /etc/bunkerweb/variables.env
    echo "BLACKLIST_IP_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "SESSIONS_NAME=test" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_REVERSE_SCAN=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REVERSE_SCAN_PORTS=80" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_ANTIBOT=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_GREYLIST=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_IP=0.0.0.0/0" | sudo tee -a /etc/bunkerweb/variables.env
    echo "WHITELIST_COUNTRY=AU" | sudo tee -a /etc/bunkerweb/variables.env

    echo "🧰 Installing Redis ..."
    export NEEDRESTART_SUSPEND=1
    export DEBIAN_FRONTEND=noninteractive
    sudo -E apt install --no-install-recommends -y redis
    redis-server --daemonize yes
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🧰 Redis start failed ❌"
        exit 1
    fi
    echo "🧰 Redis installed ✅"

    echo "USE_REDIS=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_HOST=127.0.0.1" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_PORT=6379" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_DATABASE=0" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIS_SSL=no" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
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
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT_NUMBER: "[0-9]*"@REDIS_PORT_NUMBER: "6379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_MASTER_PORT_NUMBER: "[0-9]*"@REDIS_MASTER_PORT_NUMBER: "6379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_PORT_NUMBER: "[0-9]*"@REDIS_SENTINEL_PORT_NUMBER: "26379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "1"@REDIS_DATABASE: "0"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "yes"@REDIS_SSL: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_ENABLED: "yes"@REDIS_TLS_ENABLED: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_TLS_ENABLED: "yes"@REDIS_SENTINEL_TLS_ENABLED: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_PORT_NUMBER: "[0-9]*"@REDIS_TLS_PORT_NUMBER: "6379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_AUTH_CLIENTS: "no"@REDIS_TLS_AUTH_CLIENTS: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PASSWORD: ".*"@REDIS_PASSWORD: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_PASSWORD: ".*"@REDIS_SENTINEL_PASSWORD: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_USERNAME: ".*"@REDIS_USERNAME: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_USERNAME: ".*"@REDIS_SENTINEL_USERNAME: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_HOSTS: ".*"@REDIS_SENTINEL_HOSTS: ""@' {} \;
        else
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
            sudo systemctl stop redis
            sudo killall redis-server
        fi
        sudo rm -rf acl tls
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

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🧰 Cleanup failed ❌"
        exit 1
    fi

    echo "🧰 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

tests="activated reverse_scan antibot tweaked ssl"

if [ "$integration" == "docker" ] ; then
    tests="$tests sentinel sentinel_tweaked" # TODO sentinel_ssl
fi

for test in $tests
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
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT_NUMBER: "[0-9]*"@REDIS_PORT_NUMBER: "6380"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_MASTER_PORT_NUMBER: "[0-9]*"@REDIS_MASTER_PORT_NUMBER: "6380"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "0"@REDIS_DATABASE: "1"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PASSWORD: ".*"@REDIS_PASSWORD: "secret"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_USERNAME: ".*"@REDIS_USERNAME: "bunkerweb"@' {} \;
        else
            sudo sed -i 's@USE_ANTIBOT=.*$@USE_ANTIBOT=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_PORT=.*$@REDIS_PORT=6380@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_DATABASE=.*$@REDIS_DATABASE=1@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_PASSWORD=.*$@REDIS_PASSWORD=secret@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_USERNAME=.*$@REDIS_USERNAME=bunkerweb@' /etc/bunkerweb/variables.env
            unset USE_ANTIBOT
            export REDIS_PORT="6380"
            export REDIS_DATABASE="1"
            export REDIS_PASSWORD="secret"
            export REDIS_USERNAME="bunkerweb"

            echo "🧰 Stopping redis ..."
            sudo systemctl stop redis
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🧰 Redis stop failed ❌"
                exit 1
            fi
            echo "🧰 Redis stopped ✅"
            echo "🧰 Starting redis with tweaked settings ..."
            redis-server --port 6380 --requirepass secret --aclfile acl/redis.acl --daemonize yes
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🧰 Redis start failed ❌"
                exit 1
            fi
            echo "🧰 Redis started ✅"
        fi
    elif [ "$test" = "ssl" ] ; then
        echo "🧰 Running tests with redis' ssl activated ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT_NUMBER: "[0-9]*"@REDIS_PORT_NUMBER: "6379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_MASTER_PORT_NUMBER: "[0-9]*"@REDIS_MASTER_PORT_NUMBER: "6379"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "1"@REDIS_DATABASE: "0"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PASSWORD: ".*"@REDIS_PASSWORD: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_USERNAME: ".*"@REDIS_USERNAME: ""@' {} \;

            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "no"@REDIS_SSL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_ENABLED: "no"@REDIS_TLS_ENABLED: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_PORT_NUMBER: "[0-9]*"@REDIS_TLS_PORT_NUMBER: "6380"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_AUTH_CLIENTS: "yes"@REDIS_TLS_AUTH_CLIENTS: "no"@' {} \;
        else
            sudo sed -i 's@REDIS_PORT=.*$@REDIS_PORT=6379@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_DATABASE=.*$@REDIS_DATABASE=0@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_PASSWORD=.*$@REDIS_PASSWORD=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_USERNAME=.*$@REDIS_USERNAME=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIS_SSL=.*$@REDIS_SSL=yes@' /etc/bunkerweb/variables.env
            unset REDIS_PORT
            unset REDIS_DATABASE
            unset REDIS_PASSWORD
            unset REDIS_USERNAME
            export REDIS_SSL="yes"

            echo "🧰 Stopping redis ..."
            sudo killall redis-server
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🧰 Redis stop failed ❌"
                exit 1
            fi
            echo "🧰 Redis stopped ✅"
            echo "🧰 Starting redis with tweaked settings ..."
            redis-server --tls-port 6379 --port 0 --tls-cert-file tls/redis.pem --tls-key-file tls/redis.key --tls-ca-cert-file tls/ca.crt --tls-auth-clients no --daemonize yes
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🧰 Redis start failed ❌"
                exit 1
            fi
            echo "🧰 Redis started ✅"
        fi
    elif [ "$test" = "sentinel" ] ; then
        echo "🧰 Running tests with redis' in sentinel mode ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "yes"@REDIS_SSL: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_ENABLED: "yes"@REDIS_TLS_ENABLED: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_PORT_NUMBER: "[0-9]*"@REDIS_TLS_PORT_NUMBER: "6379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_AUTH_CLIENTS: "no"@REDIS_TLS_AUTH_CLIENTS: "yes"@' {} \;

        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_HOSTS: ".*"@REDIS_SENTINEL_HOSTS: "redis-bw-redis-sentinel-1:26379 redis-bw-redis-sentinel-2:26379 redis-bw-redis-sentinel-3:26379"@' {} \;
    elif [ "$test" = "sentinel_tweaked" ] ; then
        echo "🧰 Running tests with redis' in sentinel mode with tweaked settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6380"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT_NUMBER: "[0-9]*"@REDIS_PORT_NUMBER: "6380"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_MASTER_PORT_NUMBER: "[0-9]*"@REDIS_MASTER_PORT_NUMBER: "6380"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_PORT_NUMBER: "[0-9]*"@REDIS_SENTINEL_PORT_NUMBER: "26380"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "0"@REDIS_DATABASE: "1"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PASSWORD: ".*"@REDIS_PASSWORD: "secret"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_PASSWORD: ".*"@REDIS_SENTINEL_PASSWORD: "sentinel_secret"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_USERNAME: ".*"@REDIS_USERNAME: "bunkerweb"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_USERNAME: ".*"@REDIS_SENTINEL_USERNAME: "bunkerweb_sentinel"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_HOSTS: ".*"@REDIS_SENTINEL_HOSTS: "redis-bw-redis-sentinel-1:26380 redis-bw-redis-sentinel-2:26380 redis-bw-redis-sentinel-3:26380"@' {} \;
    elif [ "$test" = "sentinel_ssl" ] ; then
        echo "🧰 Running tests with redis' in sentinel mode with ssl activated ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT: "[0-9]*"@REDIS_PORT: "6379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PORT_NUMBER: "[0-9]*"@REDIS_PORT_NUMBER: "6379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_MASTER_PORT_NUMBER: "[0-9]*"@REDIS_MASTER_PORT_NUMBER: "6379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "no"@REDIS_SSL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_DATABASE: "1"@REDIS_DATABASE: "0"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_PASSWORD: ".*"@REDIS_PASSWORD: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_USERNAME: ".*"@REDIS_USERNAME: ""@' {} \;

        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SSL: "no"@REDIS_SSL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_ENABLED: "no"@REDIS_TLS_ENABLED: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_PORT_NUMBER: "[0-9]*"@REDIS_TLS_PORT_NUMBER: "6380"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_TLS_ENABLED: "no"@REDIS_SENTINEL_TLS_ENABLED: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_PORT_NUMBER: "[0-9]*"@REDIS_SENTINEL_PORT_NUMBER: "26379"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_TLS_AUTH_CLIENTS: "yes"@REDIS_TLS_AUTH_CLIENTS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_TLS_AUTH_CLIENTS: "yes"@REDIS_SENTINEL_TLS_AUTH_CLIENTS: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIS_SENTINEL_HOSTS: ".*"@REDIS_SENTINEL_HOSTS: "redis-bw-redis-sentinel-1:26379 redis-bw-redis-sentinel-2:26379 redis-bw-redis-sentinel-3:26379"@' {} \;
    fi

    echo "🧰 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🧰 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🧰 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
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
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
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
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
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

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🧰 ⚠ Linux stack got an issue, restarting ..."
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
            echo "🧰 Linux stack could not be healthy ❌"
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
