#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "↩️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "↩️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "↩️ Building redirect stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" = "docker" ] ; then
    docker compose pull bw-docker app1
    if [ $? -ne 0 ] ; then
        echo "↩️ Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    if [ $? -ne 0 ] ; then
        echo "↩️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "REDIRECT_TO=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REDIRECT_TO_REQUEST_URI=no" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" = "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIRECT_TO: "http://brightlushsilveryawn\.neverssl\.com/online/"@REDIRECT_TO: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIRECT_TO_REQUEST_URI: "yes"@REDIRECT_TO_REQUEST_URI: "no"@' {} \;
        else
            sudo sed -i 's@REDIRECT_TO=.*$@REDIRECT_TO=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REDIRECT_TO_REQUEST_URI=.*$@REDIRECT_TO_REQUEST_URI=no@' /etc/bunkerweb/variables.env
            unset REDIRECT_TO
            unset REDIRECT_TO_REQUEST_URI
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "↩️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    if [ $? -ne 0 ] ; then
        echo "↩️ Cleanup failed ❌"
        exit 1
    fi

    echo "↩️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "redirect" "redirect_uri"
do
    if [ "$test" = "redirect" ] ; then
        echo "↩️ Running tests when redirecting to http://brightlushsilveryawn.neverssl.com/online/ ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIRECT_TO: ""@REDIRECT_TO: "http://brightlushsilveryawn.neverssl.com/online/"@' {} \;
        else
            echo "REDIRECT_TO=http://brightlushsilveryawn.neverssl.com/online/" | sudo tee -a /etc/bunkerweb/variables.env
            export REDIRECT_TO="http://brightlushsilveryawn.neverssl.com/online/"
        fi
    elif [ "$test" = "redirect_uri" ] ; then
        echo "↩️ Running tests when redirecting to uri test ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REDIRECT_TO_REQUEST_URI: "no"@REDIRECT_TO_REQUEST_URI: "yes"@' {} \;
        else
            echo "REDIRECT_TO_REQUEST_URI=yes" | sudo tee -a /etc/bunkerweb/variables.env
            export REDIRECT_TO_REQUEST_URI="yes"
        fi
    fi

    echo "↩️ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "↩️ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            if [ $? -ne 0 ] ; then
                echo "↩️ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        if [ $? -ne 0 ] ; then
            echo "↩️ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "↩️ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("redirect-bw-1" "redirect-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "↩️ Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "↩️ Docker stack is not healthy ❌"
            exit 1
        fi
    else
        while [ $i -lt 120 ] ; do
            check="$(sudo cat /var/log/bunkerweb/error.log | grep "BunkerWeb is ready")"
            if ! [ -z "$check" ] ; then
                echo "↩️ Linux stack is healthy ✅"
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
            echo "↩️ Linux stack is not healthy ❌"
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
        echo "↩️ Test \"$test\" failed ❌"
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
        echo "↩️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "↩️ Tests are done ! ✅"
