#!/bin/bash

echo "💾 Building db stack ..."

# Starting stack
docker compose pull bw-docker app1
if [ $? -ne 0 ] ; then
    echo "💾 Pull failed ❌"
    exit 1
fi

docker compose -f docker-compose.mariadb.yml pull bw-db
if [ $? -ne 0 ] ; then
    echo "💾 Pull failed ❌"
    exit 1
fi

docker compose -f docker-compose.mysql.yml pull bw-db
if [ $? -ne 0 ] ; then
    echo "💾 Pull failed ❌"
    exit 1
fi

docker compose -f docker-compose.postgres.yml pull bw-db
if [ $? -ne 0 ] ; then
    echo "💾 Pull failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        rm -rf init/plugins
        rm -rf init/bunkerweb
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "sqlite:////var/lib/bunkerweb/db.sqlite3"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@MULTISITE: "yes"$@MULTISITE: "no"@' {} \;
        sed -i 's@bwadm.example.com_USE_REVERSE_PROXY@USE_REVERSE_PROXY@' docker-compose.yml
        sed -i 's@bwadm.example.com_REVERSE_PROXY_HOST@REVERSE_PROXY_HOST@' docker-compose.yml
        sed -i 's@bwadm.example.com_REVERSE_PROXY_URL@REVERSE_PROXY_URL@' docker-compose.yml
        sed -i 's@SERVICE_USE_REVERSE_PROXY@GLOBAL_USE_REVERSE_PROXY@' docker-compose.test.yml
        sed -i 's@SERVICE_REVERSE_PROXY_HOST@GLOBAL_REVERSE_PROXY_HOST@' docker-compose.test.yml
        sed -i 's@SERVICE_REVERSE_PROXY_URL@GLOBAL_REVERSE_PROXY_URL@' docker-compose.test.yml

        if [[ $(sed '16!d' docker-compose.yml) = '      bwadm.example.com_SERVER_NAME: "bwadm.example.com"' ]] ; then
            sed -i '16d' docker-compose.yml
        fi

        if [[ $(sed '20!d' docker-compose.yml) = "      bwadm.example.com_CUSTOM_CONF_MODSEC_CRS_test_service_conf: 'SecRule REQUEST_FILENAME \"@rx ^/test\" \"id:2,ctl:ruleRemoveByTag=attack-generic,ctl:ruleRemoveByTag=attack-protocol,nolog\"'" ]] ; then
            sed -i '20d' docker-compose.yml
        fi

        if [[ $(sed '16!d' docker-compose.test.yml) = '      SERVICE_SERVER_NAME: "bwadm.example.com"' ]] ; then
            sed -i '16d' docker-compose.test.yml
        fi

        if [[ $(sed '20!d' docker-compose.test.yml) = "      CUSTOM_CONF_SERVICE_MODSEC_CRS_test_service_conf: 'SecRule REQUEST_FILENAME \"@rx ^/test\" \"id:2,ctl:ruleRemoveByTag=attack-generic,ctl:ruleRemoveByTag=attack-protocol,nolog\"'" ]] ; then
            sed -i '20d' docker-compose.test.yml
        fi

        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "💾 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "💾 Down failed ❌"
        exit 1
    fi

    echo "💾 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "💾 Creating the bw-docker network ..."
docker network create bw-docker 2>/dev/null

echo "💾 Starting stack ..."
docker compose up -d 2>/dev/null
if [ $? -ne 0 ] ; then
    echo "💾 Up failed, retrying ... ⚠️"
    manual=1
    cleanup_stack
    manual=0
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "💾 Up failed ❌"
        exit 1
    fi
fi

echo "💾 Initializing workspace ..."
rm -rf init/plugins init/bunkerweb
mkdir -p init/plugins init/bunkerweb
docker compose -f docker-compose.init.yml up --build
if [ $? -ne 0 ] ; then
    echo "💾 Build failed ❌"
    exit 1
elif ! [[ -d "init/plugins/clamav" ]]; then
    echo "💾 ClamAV plugin not found ❌"
    exit 1
elif ! [[ -d "init/bunkerweb/core" ]]; then
    echo "💾 BunkerWeb's core plugins directory not found ❌"
    exit 1
elif ! [[ -d "init/bunkerweb/db" ]]; then
    echo "💾 BunkerWeb's database directory not found ❌"
    exit 1
elif ! [[ -f "init/bunkerweb/settings.json" ]]; then
    echo "💾 BunkerWeb's settings file not found ❌"
    exit 1
fi

manual=1
cleanup_stack
manual=0

docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "💾 Build failed ❌"
    exit 1
fi

for test in "local" "multisite" "mariadb" "mysql" "postgres"
do
    if [ "$test" = "local" ] ; then
        echo "💾 Running tests with a local database ..."

        echo "💾 Creating the bw-docker network ..."
        docker network create bw-docker 2>/dev/null
    elif [ "$test" = "multisite" ] ; then
        echo "💾 Running tests with MULTISITE set to yes and with multisite settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@MULTISITE: "no"$@MULTISITE: "yes"@' {} \;
        sed -i '16i \      bwadm.example.com_SERVER_NAME: "bwadm.example.com"' docker-compose.yml
        sed -i "21i \      bwadm.example.com_CUSTOM_CONF_MODSEC_CRS_test_service_conf: 'SecRule REQUEST_FILENAME \"@rx ^/test\" \"id:2,ctl:ruleRemoveByTag=attack-generic,ctl:ruleRemoveByTag=attack-protocol,nolog\"'" docker-compose.yml
        sed -i 's@USE_REVERSE_PROXY@bwadm.example.com_USE_REVERSE_PROXY@' docker-compose.yml
        sed -i 's@REVERSE_PROXY_HOST@bwadm.example.com_REVERSE_PROXY_HOST@' docker-compose.yml
        sed -i 's@REVERSE_PROXY_URL@bwadm.example.com_REVERSE_PROXY_URL@' docker-compose.yml
        sed -i '16i \      SERVICE_SERVER_NAME: "bwadm.example.com"' docker-compose.test.yml
        sed -i "21i \      CUSTOM_CONF_SERVICE_MODSEC_CRS_test_service_conf: 'SecRule REQUEST_FILENAME \"@rx ^/test\" \"id:2,ctl:ruleRemoveByTag=attack-generic,ctl:ruleRemoveByTag=attack-protocol,nolog\"'" docker-compose.test.yml
        sed -i 's@GLOBAL_USE_REVERSE_PROXY@SERVICE_USE_REVERSE_PROXY@' docker-compose.test.yml
        sed -i 's@GLOBAL_REVERSE_PROXY_HOST@SERVICE_REVERSE_PROXY_HOST@' docker-compose.test.yml
        sed -i 's@GLOBAL_REVERSE_PROXY_URL@SERVICE_REVERSE_PROXY_URL@' docker-compose.test.yml

        echo "💾 Creating the bw-docker network ..."
        docker network create bw-docker 2>/dev/null
    elif [ "$test" = "mariadb" ] ; then
        echo "💾 Running tests with MariaDB database ..."
        echo "ℹ️ Keeping the MULTISITE variable to yes and multisite settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "mariadb+pymysql://bunkerweb:secret\@bw-db:3306/db"@' {} \;

        echo "💾 Starting mariadb ..."
        docker compose -f docker-compose.mariadb.yml up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose -f docker-compose.mariadb.yml up -d 2>/dev/null
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    elif [ "$test" = "mysql" ] ; then
        echo "💾 Running tests with MySQL database ..."
        echo "ℹ️ Keeping the MULTISITE variable to yes and multisite settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "mysql+pymysql://bunkerweb:secret\@bw-db:3306/db"@' {} \;

        echo "💾 Starting mysql ..."
        docker compose -f docker-compose.mysql.yml up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose -f docker-compose.mysql.yml up -d 2>/dev/null
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    elif [ "$test" = "postgres" ] ; then
        echo "💾 Running tests with PostgreSQL database ..."
        echo "ℹ️ Keeping the MULTISITE variable to yes and multisite settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "postgresql://bunkerweb:secret\@bw-db:5432/db"@' {} \;

        echo "💾 Starting postgres ..."
        docker compose -f docker-compose.postgres.yml up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose -f docker-compose.postgres.yml up -d 2>/dev/null
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    fi

    echo "💾 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "💾 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        if [ "$test" = "mariadb" ] ; then
            docker compose -f docker-compose.mariadb.yml up -d 2>/dev/null
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        elif [ "$test" = "mysql" ] ; then
            docker compose -f docker-compose.mysql.yml up -d 2>/dev/null
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        elif [ "$test" = "postgres" ] ; then
            docker compose -f docker-compose.postgres.yml up -d 2>/dev/null
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "💾 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("db-bw-1" "db-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "💾 Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "💾 Docker stack is not healthy ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "💾 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "💾 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "💾 Tests are done ! ✅"
