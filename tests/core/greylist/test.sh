#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🏁 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🏁 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🏁 Building greylist stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    echo "🏁 Building custom api image ..."
    docker compose build greylist-api
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏁 Build failed ❌"
        exit 1
    fi

    echo "🏁 Building tests images ..."
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏁 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "USE_REAL_IP=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REAL_IP_FROM=127.0.0.0/24" | sudo tee -a /etc/bunkerweb/variables.env

    echo "USE_GREYLIST=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_IP=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_IP_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_RDNS_GLOBAL=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_RDNS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_RDNS_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_ASN=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_ASN_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_USER_AGENT=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_USER_AGENT_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_URI=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GREYLIST_URI_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
AS_NUMBER=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            rm -rf init/output
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_GREYLIST: "yes"@USE_GREYLIST: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP: "192.168.0.0/24"@GREYLIST_IP: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP_URLS: "http://greylist-api:8080/ip"@GREYLIST_IP_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_GLOBAL: "no"@GREYLIST_RDNS_GLOBAL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS: ".bw-services"@GREYLIST_RDNS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_URLS: "http://greylist-api:8080/rdns"@GREYLIST_RDNS_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN: "[0-9]*"@GREYLIST_ASN: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN_URLS: "http://greylist-api:8080/asn"@GREYLIST_ASN_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT: "BunkerBot"@GREYLIST_USER_AGENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT_URLS: "http://greylist-api:8080/user_agent"@GREYLIST_USER_AGENT_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI: "/admin"@GREYLIST_URI: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI_URLS: "http://greylist-api:8080/uri"@GREYLIST_URI_URLS: ""@' {} \;
        else
            sudo sed -i 's@USE_GREYLIST=.*$@USE_GREYLIST=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_IP=.*$@GREYLIST_IP=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_IP_URLS=.*$@GREYLIST_IP_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_RDNS_GLOBAL=.*$@GREYLIST_RDNS_GLOBAL=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_RDNS=.*$@GREYLIST_RDNS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_RDNS_URLS=.*$@GREYLIST_RDNS_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_ASN=.*$@GREYLIST_ASN=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_ASN_URLS=.*$@GREYLIST_ASN_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_USER_AGENT=.*$@GREYLIST_USER_AGENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_USER_AGENT_URLS=.*$@GREYLIST_USER_AGENT_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_URI=.*$@GREYLIST_URI=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_URI_URLS=.*$@GREYLIST_URI_URLS=@' /etc/bunkerweb/variables.env
            unset USE_GREYLIST
            unset GREYLIST_IP
            unset GREYLIST_IP_URLS
            unset GREYLIST_RDNS_GLOBAL
            unset GREYLIST_RDNS
            unset GREYLIST_RDNS_URLS
            unset GREYLIST_ASN
            unset GREYLIST_ASN_URLS
            unset GREYLIST_USER_AGENT
            unset GREYLIST_USER_AGENT_URLS
            unset GREYLIST_URI
            unset GREYLIST_URI_URLS
            sudo killall python3
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🏁 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏁 Cleanup failed ❌"
        exit 1
    fi

    echo "🏁 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🏁 Initializing workspace ..."
if [ "$integration" == "docker" ] ; then
    rm -rf init/output
    mkdir -p init/output
    docker compose -f docker-compose.init.yml up --build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏁 Init failed ❌"
        exit 1
    elif ! [[ -f "init/output/ip_asn.txt" ]]; then
        echo "🏁 ip_asn.txt not found ❌"
        exit 1
    fi

    AS_NUMBER=$(cat init/output/ip_asn.txt)
    rm -rf init/output
else
    echo "🏁 Starting init ..."
    python3 init/main.py
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏁 Init failed ❌"
        exit 1
    elif ! [[ -f "ip_asn.txt" ]]; then
        echo "🏁 ip_asn.txt not found ❌"
        exit 1
    fi

    AS_NUMBER=$(cat ip_asn.txt)
fi

if [[ $AS_NUMBER = "" ]]; then
    echo "🏁 AS number not found ❌"
    exit 1
fi

export AS_NUMBER

if [ "$integration" == "docker" ] ; then
    sudo sed -i 's@AS_NUMBER: ".*"$@AS_NUMBER: "'"$AS_NUMBER"'"@' docker-compose.yml
else
    echo "🏁 Starting api ..."
    python3 api/main.py &
fi

tests="deactivated ip ip_urls asn asn_urls user_agent user_agent_urls uri uri_urls"

if [ "$integration" == "docker" ] ; then
    tests="deactivated ip ip_urls rdns rdns_global rdns_urls asn asn_urls user_agent user_agent_urls uri uri_urls"
fi

for test in $tests
do
    if [ "$test" = "deactivated" ] ; then
        echo "🏁 Running tests when the greylist is deactivated ..."
    elif [ "$test" = "ip" ] ; then
        echo "ℹ️ Activating the greylist for all the future tests ..."
        if [ "$integration" == "docker" ] ; then
            echo "🏁 Running tests with the network 192.168.0.0/24 in the grey list ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_GREYLIST: "no"@USE_GREYLIST: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP: ""@GREYLIST_IP: "192.168.0.0/24"@' {} \;
        else
            echo "🏁 Running tests with the network 127.0.0.0/24 in the grey list ..."
            sudo sed -i 's@USE_GREYLIST=.*$@USE_GREYLIST=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_IP=.*$@GREYLIST_IP=127.0.0.0/24@' /etc/bunkerweb/variables.env
            export USE_GREYLIST="yes"
            export GREYLIST_IP="127.0.0.0/24"
        fi
    elif [ "$test" = "ip_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏁 Running tests with greylist's ip url set to http://greylist-api:8080/ip ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP: "192.168.0.0/24"@GREYLIST_IP: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP_URLS: ""@GREYLIST_IP_URLS: "http://greylist-api:8080/ip"@' {} \;
        else
            echo "🏁 Running tests with greylist's ip url set to http://127.0.0.1:8080/ip ..."
            sudo sed -i 's@GREYLIST_IP=.*$@GREYLIST_IP=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_IP_URLS=.*$@GREYLIST_IP_URLS=http://127.0.0.1:8080/ip@' /etc/bunkerweb/variables.env
            unset GREYLIST_IP
            export GREYLIST_IP_URLS="http://127.0.0.1:8080/ip"
        fi
    elif [ "$test" = "rdns" ] ; then
        echo "🏁 Running tests with greylist's rdns set to .bw-services ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP_URLS: "http://greylist-api:8080/ip"@GREYLIST_IP_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS: ""@GREYLIST_RDNS: ".bw-services"@' {} \;
    elif [ "$test" = "rdns_global" ] ; then
        echo "🏁 Running tests when greylist's rdns also scans local ip addresses ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_GLOBAL: "yes"@GREYLIST_RDNS_GLOBAL: "no"@' {} \;
    elif [ "$test" = "rdns_urls" ] ; then
        echo "🏁 Running tests with greylist's rdns url set to http://greylist-api:8080/rdns ..."
        echo "ℹ️ Keeping the rdns also scanning local ip addresses ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS: ".bw-services"@GREYLIST_RDNS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_URLS: ""@GREYLIST_RDNS_URLS: "http://greylist-api:8080/rdns"@' {} \;
    elif [ "$test" = "asn" ] ; then
        echo "🏁 Running tests with greylist's asn set to $AS_NUMBER ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_GLOBAL: "no"@GREYLIST_RDNS_GLOBAL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_URLS: "http://greylist-api:8080/rdns"@GREYLIST_RDNS_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN: ""@GREYLIST_ASN: "'"$AS_NUMBER"'"@' {} \;
        else
            sudo sed -i 's@GREYLIST_IP_URLS=.*$@GREYLIST_IP_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_ASN=.*$@GREYLIST_ASN='"$AS_NUMBER"'@' /etc/bunkerweb/variables.env
            unset GREYLIST_IP_URLS
            export GREYLIST_ASN="$AS_NUMBER"
        fi
    elif [ "$test" = "asn_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏁 Running tests with greylist's asn url set to http://greylist-api:8080/asn ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN: "'"$AS_NUMBER"'"@GREYLIST_ASN: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN_URLS: ""@GREYLIST_ASN_URLS: "http://greylist-api:8080/asn"@' {} \;
        else
            echo "🏁 Running tests with greylist's asn url set to http://127.0.0.1:8080/asn ..."
            sudo sed -i 's@GREYLIST_ASN=.*$@GREYLIST_ASN=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_ASN_URLS=.*$@GREYLIST_ASN_URLS=http://127.0.0.1:8080/asn@' /etc/bunkerweb/variables.env
            unset GREYLIST_ASN
            export GREYLIST_ASN_URLS="http://127.0.0.1:8080/asn"
        fi
    elif [ "$test" = "user_agent" ] ; then
        echo "🏁 Running tests with greylist's user_agent set to BunkerBot ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN_URLS: "http://greylist-api:8080/asn"@GREYLIST_ASN_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT: ""@GREYLIST_USER_AGENT: "BunkerBot"@' {} \;
        else
            sudo sed -i 's@GREYLIST_ASN_URLS=.*$@GREYLIST_ASN_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_USER_AGENT=.*$@GREYLIST_USER_AGENT=BunkerBot@' /etc/bunkerweb/variables.env
            unset GREYLIST_ASN_URLS
            export GREYLIST_USER_AGENT="BunkerBot"
        fi
    elif [ "$test" = "user_agent_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏁 Running tests with greylist's user_agent url set to http://greylist-api:8080/user_agent ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT: "BunkerBot"@GREYLIST_USER_AGENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT_URLS: ""@GREYLIST_USER_AGENT_URLS: "http://greylist-api:8080/user_agent"@' {} \;
        else
            echo "🏁 Running tests with greylist's user_agent url set to http://127.0.0.1:8080/user_agent ..."
            sudo sed -i 's@GREYLIST_USER_AGENT=.*$@GREYLIST_USER_AGENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_USER_AGENT_URLS=.*$@GREYLIST_USER_AGENT_URLS=http://127.0.0.1:8080/user_agent@' /etc/bunkerweb/variables.env
            unset GREYLIST_USER_AGENT
            export GREYLIST_USER_AGENT_URLS="http://127.0.0.1:8080/user_agent"
        fi
    elif [ "$test" = "uri" ] ; then
        echo "🏁 Running tests with greylist's uri set to /admin ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT_URLS: "http://greylist-api:8080/user_agent"@GREYLIST_USER_AGENT_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI: ""@GREYLIST_URI: "/admin"@' {} \;
        else
            sudo sed -i 's@GREYLIST_USER_AGENT_URLS=.*$@GREYLIST_USER_AGENT_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_URI=.*$@GREYLIST_URI=/admin@' /etc/bunkerweb/variables.env
            unset GREYLIST_USER_AGENT_URLS
            export GREYLIST_URI="/admin"
        fi
    elif [ "$test" = "uri_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏁 Running tests with greylist's uri url set to http://greylist-api:8080/uri ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI: "/admin"@GREYLIST_URI: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI_URLS: ""@GREYLIST_URI_URLS: "http://greylist-api:8080/uri"@' {} \;
        else
            echo "🏁 Running tests with greylist's uri url set to http://127.0.0.1:8080/uri ..."
            sudo sed -i 's@GREYLIST_URI=.*$@GREYLIST_URI=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GREYLIST_URI_URLS=.*$@GREYLIST_URI_URLS=http://127.0.0.1:8080/uri@' /etc/bunkerweb/variables.env
            unset GREYLIST_URI
            export GREYLIST_URI_URLS="http://127.0.0.1:8080/uri"
        fi
    fi

    echo "🏁 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🏁 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🏁 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🏁 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🏁 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("greylist-bw-1" "greylist-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🏁 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🏁 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🏁 Linux stack is healthy ✅"
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
                echo "🏁 Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🏁 ⚠ Linux stack got an issue, restarting ..."
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
            echo "🏁 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests

    if ! [[ "$test" = "user_agent" || "$test" = "user_agent_urls" || "$test" = "uri" || "$test" = "uri_urls" ]] ; then
        echo "🏁 Running global container tests ..."

        if [ "$integration" == "docker" ] ; then
            docker compose -f docker-compose.test.yml up global-tests --abort-on-container-exit --exit-code-from global-tests
        else
            export GLOBAL="1"
            python3 main.py
        fi

        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🏁 Test \"$test\" failed for global tests ❌"
            echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
            if [ "$integration" == "docker" ] ; then
                docker compose logs bw bw-scheduler greylist-api
            else
                sudo journalctl -u bunkerweb --no-pager
                echo "🛡️ Showing BunkerWeb error logs ..."
                sudo cat /var/log/bunkerweb/error.log
                echo "🛡️ Showing BunkerWeb access logs ..."
                sudo cat /var/log/bunkerweb/access.log
            fi
            exit 1
        else
            echo "🏁 Test \"$test\" succeeded for global tests ✅"
        fi

        if [ "$integration" == "linux" ] ; then
            sleep 1
        fi
    fi

    echo "🏁 Running local container tests ..."

    if [ "$integration" == "docker" ] ; then
        docker compose -f docker-compose.test.yml up local-tests --abort-on-container-exit --exit-code-from local-tests
    else
        unset GLOBAL
        python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏁 Test \"$test\" failed for local tests ❌"
        echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
        if [ "$integration" == "docker" ] ; then
            docker compose logs bw bw-scheduler greylist-api
        else
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
        fi
        exit 1
    else
        echo "🏁 Test \"$test\" succeeded for local tests ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🏁 Tests are done ! ✅"
