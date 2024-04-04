#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "💾 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "💾 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "💾 Building backup stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose pull bw-docker
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.mariadb.yml pull bw-db
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.mysql.yml pull bw-db
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.postgres.yml pull bw-db
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "DATABASE_URI=sqlite:////var/lib/bunkerweb/db.sqlite3" | sudo tee -a /etc/bunkerweb/variables.env
    echo "USE_BACKUP=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BACKUP_DIRECTORY=/var/lib/bunkerweb/backups" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BACKUP_ROTATION=7" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
fi

manual=0
end=0
# shellcheck disable=SC2120
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "sqlite:////var/lib/bunkerweb/db.sqlite3"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BACKUP: ".*"$@USE_BACKUP: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BACKUP_DIRECTORY: ".*"$@BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BACKUP_ROTATION: ".*"$@BACKUP_ROTATION: "7"@' {} \;
        else
            sudo sed -i '/^DATABASE_URI/d' /etc/bunkerweb/variables.env
            sudo sed -i '/^USE_BACKUP/d' /etc/bunkerweb/variables.env
            sudo sed -i '/^BACKUP_DIRECTORY/d' /etc/bunkerweb/variables.env
            sudo sed -i '/^BACKUP_ROTATION/d' /etc/bunkerweb/variables.env
            unset DATABASE_URI
            unset USE_BACKUP
            unset BACKUP_DIRECTORY
            unset BACKUP_SCHEDULE
            unset BACKUP_ROTATION
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "💾 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        soft_cleanup=$1
        if [ "$soft_cleanup" = "1" ] ; then
            docker compose down
        else
            docker compose down -v --remove-orphans
        fi

        if [[ $end -eq 0 && $exit_code = 1 ]] && [ $manual = 0 ] ; then
            echo "💾 Removing bw-docker network ..."

            docker network rm bw-docker

            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "💾 Network removal failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Cleanup failed ❌"
        exit 1
    fi

    echo "💾 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

starting_stack () {
    echo "💾 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            if [ "$test" = "mariadb" ] ; then
                docker compose -f docker-compose.mariadb.yml up -d
                if [ $? -ne 0 ] ; then
                    echo "💾 Up failed ❌"
                    exit 1
                fi
            elif [ "$test" = "mysql" ] ; then
                docker compose -f docker-compose.mysql.yml up -d
                if [ $? -ne 0 ] ; then
                    echo "💾 Up failed ❌"
                    exit 1
                fi
            elif [ "$test" = "postgres" ] ; then
                docker compose -f docker-compose.postgres.yml up -d
                if [ $? -ne 0 ] ; then
                    echo "💾 Up failed ❌"
                    exit 1
                fi
            fi
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "💾 Start failed ❌"
            exit 1
        fi
    fi
}

waiting_stack () {
    # Check if stack is healthy
    echo "💾 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("backup-bw-1" "backup-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
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
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "💾 Linux stack is healthy ✅"
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
                echo "💾 Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "💾 ⚠ Linux stack got an issue, restarting ..."
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
            echo "💾 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi
}

tests="activated deactivated tweaked"

if [ "$integration" == "docker" ] ; then
    tests="$tests mariadb mysql postgres"
fi

for test in $tests
do
    if [ "$integration" == "docker" ] ; then
        echo "💾 Creating the bw-docker network ..."
        docker network create bw-docker
    fi

    if [ "$test" = "activated" ] ; then
        echo "💾 Running tests with the default settings ..."
    elif [ "$test" = "deactivated" ] ; then
        echo "💾 Running tests with the backup deactivated ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BACKUP: ".*"$@USE_BACKUP: "no"@' {} \;
        else
            sudo sed -i 's@USE_BACKUP=yes@USE_BACKUP=no@' /etc/bunkerweb/variables.env
            export USE_BACKUP="no"
        fi
    elif [ "$test" = "tweaked" ] ; then
        echo "💾 Running tests with tweaked backup settings ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BACKUP: ".*"$@USE_BACKUP: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BACKUP_DIRECTORY: ".*"$@BACKUP_DIRECTORY: "/var/lib/bunkerweb/tmp_backups"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BACKUP_ROTATION: ".*"$@BACKUP_ROTATION: "2"@' {} \;
        else
            sudo sed -i 's@USE_BACKUP=no@USE_BACKUP=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BACKUP_DIRECTORY=/var/lib/bunkerweb/backups@BACKUP_DIRECTORY=/var/lib/bunkerweb/tmp_backups@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BACKUP_ROTATION=7@BACKUP_ROTATION=2@' /etc/bunkerweb/variables.env
            unset USE_BACKUP
            export BACKUP_DIRECTORY="/var/lib/bunkerweb/tmp_backups"
            export BACKUP_ROTATION="2"
        fi
    elif [ "$test" = "mariadb" ] ; then
        echo "💾 Running tests with MariaDB database ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "mariadb+pymysql://bunkerweb:secret\@bw-db:3306/db"@' {} \;

        echo "💾 Starting mariadb ..."
        docker compose -f docker-compose.mariadb.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose -f docker-compose.mariadb.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    elif [ "$test" = "mysql" ] ; then
        echo "💾 Running tests with MySQL database ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "mysql+pymysql://bunkerweb:secret\@bw-db:3306/db"@' {} \;

        echo "💾 Starting mysql ..."
        docker compose -f docker-compose.mysql.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose -f docker-compose.mysql.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    elif [ "$test" = "postgres" ] ; then
        echo "💾 Running tests with PostgreSQL database ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@DATABASE_URI: ".*"$@DATABASE_URI: "postgresql+psycopg://bunkerweb:secret\@bw-db:5432/db"@' {} \;

        echo "💾 Starting postgres ..."
        docker compose -f docker-compose.postgres.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "💾 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose -f docker-compose.postgres.yml up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "💾 Up failed ❌"
                exit 1
            fi
        fi
    fi

    starting_stack

    waiting_stack

    # Start tests

    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests
    else
        sudo -E python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "💾 Test \"$test\" failed ❌"
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
        echo "💾 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "

    if [ "$integration" == "docker" ] ; then
        echo "💾 Removing bw-docker network ..."

        docker network rm bw-docker

        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "💾 Network removal failed ❌"
            exit 1
        fi
    fi
done

end=1
echo "💾 Tests are done ! ✅"
