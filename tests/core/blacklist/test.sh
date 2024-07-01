#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🏴 Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🏴 Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🏴 Building blacklist stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    echo "🏴 Building custom api image ..."
    docker compose build blacklist-api
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏴 Build failed ❌"
        exit 1
    fi

    echo "🏴 Building tests images ..."
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏴 Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    echo "USE_REAL_IP=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REAL_IP_FROM=127.0.0.0/24" | sudo tee -a /etc/bunkerweb/variables.env

    sudo sed -i 's@USE_BLACKLIST=.*$@USE_BLACKLIST=yes@' /etc/bunkerweb/variables.env
    echo "BLACKLIST_IP=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IP_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_RDNS_GLOBAL=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_RDNS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_RDNS_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_ASN=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_ASN_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_USER_AGENT=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_USER_AGENT_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_URI=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_URI_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_IP=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_IP_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_RDNS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_RDNS_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_ASN=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_ASN_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_USER_AGENT=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_USER_AGENT_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_URI=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "BLACKLIST_IGNORE_URI_URLS=" | sudo tee -a /etc/bunkerweb/variables.env
    sudo touch /var/www/html/index.html
    export TEST_TYPE="linux"
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
AS_NUMBER=""
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            rm -rf init/output
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BLACKLIST: "no"@USE_BLACKLIST: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP: "0.0.0.0/0"@BLACKLIST_IP: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP: "192.168.0.3"@BLACKLIST_IGNORE_IP: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP_URLS: "http://blacklist-api:8080/ip"@BLACKLIST_IP_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP_URLS: "http://blacklist-api:8080/ip"@BLACKLIST_IGNORE_IP_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_GLOBAL: "no"@BLACKLIST_RDNS_GLOBAL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS: ".bw-services"@BLACKLIST_RDNS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_RDNS: ".bw-services"@BLACKLIST_IGNORE_RDNS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_URLS: "http://blacklist-api:8080/rdns"@BLACKLIST_RDNS_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_RDNS_URLS: "http://blacklist-api:8080/rdns"@BLACKLIST_IGNORE_RDNS_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN: "[0-9]*"@BLACKLIST_ASN: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN: "[0-9]*"@BLACKLIST_IGNORE_ASN: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN_URLS: "http://blacklist-api:8080/asn"@BLACKLIST_ASN_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN_URLS: "http://blacklist-api:8080/asn"@BLACKLIST_IGNORE_ASN_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT: "BunkerBot"@BLACKLIST_USER_AGENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT: "BunkerBot"@BLACKLIST_IGNORE_USER_AGENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@BLACKLIST_USER_AGENT_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@BLACKLIST_IGNORE_USER_AGENT_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI: "/admin"@BLACKLIST_URI: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI: "/admin"@BLACKLIST_IGNORE_URI: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI_URLS: "http://blacklist-api:8080/uri"@BLACKLIST_URI_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI_URLS: "http://blacklist-api:8080/uri"@BLACKLIST_IGNORE_URI_URLS: ""@' {} \;
        else
            rm -f ip_asn.txt
            sudo sed -i 's@USE_BLACKLIST=.*$@USE_BLACKLIST=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IP=.*$@BLACKLIST_IP=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IP_URLS=.*$@BLACKLIST_IP_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_RDNS_GLOBAL=.*$@BLACKLIST_RDNS_GLOBAL=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_RDNS=.*$@BLACKLIST_RDNS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_RDNS_URLS=.*$@BLACKLIST_RDNS_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_ASN=.*$@BLACKLIST_ASN=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_ASN_URLS=.*$@BLACKLIST_ASN_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_USER_AGENT=.*$@BLACKLIST_USER_AGENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_USER_AGENT_URLS=.*$@BLACKLIST_USER_AGENT_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_URI=.*$@BLACKLIST_URI=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_URI_URLS=.*$@BLACKLIST_URI_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_IP=.*$@BLACKLIST_IGNORE_IP=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_IP_URLS=.*$@BLACKLIST_IGNORE_IP_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_RDNS=.*$@BLACKLIST_IGNORE_RDNS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_RDNS_URLS=.*$@BLACKLIST_IGNORE_RDNS_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_ASN=.*$@BLACKLIST_IGNORE_ASN=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_ASN_URLS=.*$@BLACKLIST_IGNORE_ASN_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_USER_AGENT=.*$@BLACKLIST_IGNORE_USER_AGENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS=.*$@BLACKLIST_IGNORE_USER_AGENT_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_URI=.*$@BLACKLIST_IGNORE_URI=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_URI_URLS=.*$@BLACKLIST_IGNORE_URI_URLS=@' /etc/bunkerweb/variables.env
            unset USE_BLACKLIST
            unset BLACKLIST_IP
            unset BLACKLIST_IP_URLS
            unset BLACKLIST_RDNS_GLOBAL
            unset BLACKLIST_RDNS
            unset BLACKLIST_RDNS_URLS
            unset BLACKLIST_ASN
            unset BLACKLIST_ASN_URLS
            unset BLACKLIST_USER_AGENT
            unset BLACKLIST_USER_AGENT_URLS
            unset BLACKLIST_URI
            unset BLACKLIST_URI_URLS
            unset BLACKLIST_IGNORE_IP
            unset BLACKLIST_IGNORE_IP_URLS
            unset BLACKLIST_IGNORE_RDNS
            unset BLACKLIST_IGNORE_RDNS_URLS
            unset BLACKLIST_IGNORE_ASN
            unset BLACKLIST_IGNORE_ASN_URLS
            unset BLACKLIST_IGNORE_USER_AGENT
            unset BLACKLIST_IGNORE_USER_AGENT_URLS
            unset BLACKLIST_IGNORE_URI
            unset BLACKLIST_IGNORE_URI_URLS
            unset AS_NUMBER
            sudo killall python3
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🏴 Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏴 Cleanup failed ❌"
        exit 1
    fi

    echo "🏴 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🏴 Initializing workspace ..."
if [ "$integration" == "docker" ] ; then
    rm -rf init/output
    mkdir -p init/output
    docker compose -f docker-compose.init.yml up --build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏴 Init failed ❌"
        exit 1
    elif ! [[ -f "init/output/ip_asn.txt" ]]; then
        echo "🏴 ip_asn.txt not found ❌"
        exit 1
    fi

    AS_NUMBER=$(cat init/output/ip_asn.txt)
    rm -rf init/output
else
    echo "🏴 Starting init ..."
    python3 init/main.py
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏴 Init failed ❌"
        exit 1
    elif ! [[ -f "ip_asn.txt" ]]; then
        echo "🏴 ip_asn.txt not found ❌"
        exit 1
    fi

    AS_NUMBER=$(cat ip_asn.txt)
fi

if [[ $AS_NUMBER = "" ]]; then
    echo "🏴 AS number not found ❌"
    exit 1
fi

export AS_NUMBER

if [ "$integration" == "docker" ] ; then
    sudo sed -i 's@AS_NUMBER: ".*"$@AS_NUMBER: "'"$AS_NUMBER"'"@' docker-compose.yml
else
    echo "🏴 Starting api ..."
    python3 api/main.py &
fi

tests="ip deactivated ignore_ip ignore_ip_urls ip_urls asn ignore_asn ignore_asn_urls asn_urls user_agent ignore_user_agent ignore_user_agent_urls user_agent_urls uri ignore_uri ignore_uri_urls uri_urls"

if [ "$integration" == "docker" ] ; then
    tests="ip deactivated ignore_ip ignore_ip_urls ip_urls rdns rdns_global ignore_rdns ignore_rdns_urls rdns_urls asn ignore_asn ignore_asn_urls asn_urls user_agent ignore_user_agent ignore_user_agent_urls user_agent_urls uri ignore_uri ignore_uri_urls uri_urls"
fi

for test in $tests
do
    if [ "$test" = "ip" ] ; then
        echo "🏴 Running tests with the network 0.0.0.0/0 in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP: ""@BLACKLIST_IP: "0.0.0.0/0"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_IP=.*$@BLACKLIST_IP=0.0.0.0/0@' /etc/bunkerweb/variables.env
            export BLACKLIST_IP="0.0.0.0/0"
        fi
    elif [ "$test" = "deactivated" ] ; then
        echo "🏴 Running tests when deactivating the blacklist ..."
        echo "ℹ️ Keeping the network 0.0.0.0/0 in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BLACKLIST: "yes"@USE_BLACKLIST: "no"@' {} \;
        else
            sudo sed -i 's@USE_BLACKLIST=.*$@USE_BLACKLIST=no@' /etc/bunkerweb/variables.env
            export USE_BLACKLIST="no"
        fi
    elif [ "$test" = "ignore_ip" ] ; then
        echo "ℹ️ Keeping the network 0.0.0.0/0 in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's ignore_ip set to 192.168.0.3 ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BLACKLIST: "no"@USE_BLACKLIST: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP: ""@BLACKLIST_IGNORE_IP: "192.168.0.3"@' {} \;
        else
            echo "🏴 Running tests with blacklist's ignore_ip set to 127.0.0.1 ..."
            sudo sed -i 's@USE_BLACKLIST=.*$@USE_BLACKLIST=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_IP=.*$@BLACKLIST_IGNORE_IP=127.0.0.1@' /etc/bunkerweb/variables.env
            unset USE_BLACKLIST
            export BLACKLIST_IGNORE_IP="127.0.0.1"
        fi
    elif [ "$test" = "ignore_ip_urls" ] ; then
        echo "ℹ️ Keeping the network 0.0.0.0/0 in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's ignore_ip_urls set to http://blacklist-api:8080/ip ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP: "192.168.0.3"@BLACKLIST_IGNORE_IP: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP_URLS: ""@BLACKLIST_IGNORE_IP_URLS: "http://blacklist-api:8080/ip"@' {} \;
        else
            echo "🏴 Running tests with blacklist's ignore_ip_urls set to http://127.0.0.1:8080/ip ..."
            sudo sed -i 's@BLACKLIST_IGNORE_IP=.*$@BLACKLIST_IGNORE_IP=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_IP_URLS=.*$@BLACKLIST_IGNORE_IP_URLS=http://127.0.0.1:8080/ip@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_IP
            export BLACKLIST_IGNORE_IP_URLS="http://127.0.0.1:8080/ip"
        fi
    elif [ "$test" = "ip_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's ip url set to http://blacklist-api:8080/ip ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP_URLS: "http://blacklist-api:8080/ip"@BLACKLIST_IGNORE_IP_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP: "0.0.0.0/0"@BLACKLIST_IP: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP_URLS: ""@BLACKLIST_IP_URLS: "http://blacklist-api:8080/ip"@' {} \;
        else
            echo "🏴 Running tests with blacklist's ip url set to http://127.0.0.1:8080/ip ..."
            sudo sed -i 's@BLACKLIST_IGNORE_IP_URLS=.*$@BLACKLIST_IGNORE_IP_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IP=.*$@BLACKLIST_IP=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IP_URLS=.*$@BLACKLIST_IP_URLS=http://127.0.0.1:8080/ip@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_IP_URLS
            unset BLACKLIST_IP
            export BLACKLIST_IP_URLS="http://127.0.0.1:8080/ip"
        fi
    elif [ "$test" = "rdns" ] ; then
        echo "🏴 Running tests with blacklist's rdns set to .bw-services ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP_URLS: "http://blacklist-api:8080/ip"@BLACKLIST_IP_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS: ""@BLACKLIST_RDNS: ".bw-services"@' {} \;
    elif [ "$test" = "rdns_global" ] ; then
        echo "🏴 Running tests when blacklist's rdns also scans local ip addresses ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_GLOBAL: "yes"@BLACKLIST_RDNS_GLOBAL: "no"@' {} \;
    elif [ "$test" = "ignore_rdns" ] ; then
        echo "🏴 Running tests with blacklist's ignore_rdns set to .bw-services ..."
        echo "ℹ️ Keeping the rdns also scanning local ip addresses ..."
        echo "ℹ️ Keeping the rdns .bw-services in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_RDNS: ""@BLACKLIST_IGNORE_RDNS: ".bw-services"@' {} \;
    elif [ "$test" = "ignore_rdns_urls" ] ; then
        echo "🏴 Running tests with blacklist's ignore_rdns_urls set to http://blacklist-api:8080/rdns ..."
        echo "ℹ️ Keeping the rdns also scanning local ip addresses ..."
        echo "ℹ️ Keeping the rdns .bw-services in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_RDNS: ".bw-services"@BLACKLIST_IGNORE_RDNS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_RDNS_URLS: ""@BLACKLIST_IGNORE_RDNS_URLS: "http://blacklist-api:8080/rdns"@' {} \;
    elif [ "$test" = "rdns_urls" ] ; then
        echo "🏴 Running tests with blacklist's rdns url set to http://blacklist-api:8080/rdns ..."
        echo "ℹ️ Keeping the rdns also scanning local ip addresses ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_RDNS_URLS: "http://blacklist-api:8080/rdns"@BLACKLIST_IGNORE_RDNS_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS: ".bw-services"@BLACKLIST_RDNS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_URLS: ""@BLACKLIST_RDNS_URLS: "http://blacklist-api:8080/rdns"@' {} \;
    elif [ "$test" = "asn" ] ; then
        echo "🏴 Running tests with blacklist's asn set to $AS_NUMBER ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_GLOBAL: "no"@BLACKLIST_RDNS_GLOBAL: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_URLS: "http://blacklist-api:8080/rdns"@BLACKLIST_RDNS_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN: ""@BLACKLIST_ASN: "'"$AS_NUMBER"'"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_IP_URLS=.*$@BLACKLIST_IP_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_ASN=.*$@BLACKLIST_ASN='"$AS_NUMBER"'@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IP_URLS
            export BLACKLIST_ASN="$AS_NUMBER"
        fi
    elif [ "$test" = "ignore_asn" ] ; then
        echo "🏴 Running tests with blacklist's ignore_asn set to $AS_NUMBER ..."
        echo "ℹ️ Keeping the asn $AS_NUMBER in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN: ""@BLACKLIST_IGNORE_ASN: "'"$AS_NUMBER"'"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_IGNORE_ASN=.*$@BLACKLIST_IGNORE_ASN='"$AS_NUMBER"'@' /etc/bunkerweb/variables.env
            export BLACKLIST_IGNORE_ASN="$AS_NUMBER"
        fi
    elif [ "$test" = "ignore_asn_urls" ] ; then
        echo "ℹ️ Keeping the asn $AS_NUMBER in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's ignore_asn_urls set to http://blacklist-api:8080/asn ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN: "'"$AS_NUMBER"'"@BLACKLIST_IGNORE_ASN: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN_URLS: ""@BLACKLIST_IGNORE_ASN_URLS: "http://blacklist-api:8080/asn"@' {} \;
        else
            echo "🏴 Running tests with blacklist's ignore_asn_urls set to http://127.0.0.1:8080/asn ..."
            sudo sed -i 's@BLACKLIST_IGNORE_ASN=.*$@BLACKLIST_IGNORE_ASN=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_ASN_URLS=.*$@BLACKLIST_IGNORE_ASN_URLS=http://127.0.0.1:8080/asn@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_ASN
            export BLACKLIST_IGNORE_ASN_URLS="http://127.0.0.1:8080/asn"
        fi
    elif [ "$test" = "asn_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's asn url set to http://blacklist-api:8080/asn ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN_URLS: "http://blacklist-api:8080/asn"@BLACKLIST_IGNORE_ASN_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN: "'"$AS_NUMBER"'"@BLACKLIST_ASN: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN_URLS: ""@BLACKLIST_ASN_URLS: "http://blacklist-api:8080/asn"@' {} \;
        else
            echo "🏴 Running tests with blacklist's asn url set to http://127.0.0.1:8080/asn ..."
            sudo sed -i 's@BLACKLIST_IGNORE_ASN_URLS=.*$@BLACKLIST_IGNORE_ASN_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_ASN=.*$@BLACKLIST_ASN=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_ASN_URLS=.*$@BLACKLIST_ASN_URLS=http://127.0.0.1:8080/asn@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_ASN_URLS
            unset BLACKLIST_ASN
            export BLACKLIST_ASN_URLS="http://127.0.0.1:8080/asn"
        fi
    elif [ "$test" = "user_agent" ] ; then
        echo "🏴 Running tests with blacklist's user_agent set to BunkerBot ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN_URLS: "http://blacklist-api:8080/asn"@BLACKLIST_ASN_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT: ""@BLACKLIST_USER_AGENT: "BunkerBot"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_ASN_URLS=.*$@BLACKLIST_ASN_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_USER_AGENT=.*$@BLACKLIST_USER_AGENT=BunkerBot@' /etc/bunkerweb/variables.env
            unset BLACKLIST_ASN_URLS
            export BLACKLIST_USER_AGENT="BunkerBot"
        fi
    elif [ "$test" = "ignore_user_agent" ] ; then
        echo "🏴 Running tests with blacklist's ignore_user_agent set to BunkerBot ..."
        echo "ℹ️ Keeping the user_agent BunkerBot in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT: ""@BLACKLIST_IGNORE_USER_AGENT: "BunkerBot"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_IGNORE_USER_AGENT=.*$@BLACKLIST_IGNORE_USER_AGENT=BunkerBot@' /etc/bunkerweb/variables.env
            export BLACKLIST_IGNORE_USER_AGENT="BunkerBot"
        fi
    elif [ "$test" = "ignore_user_agent_urls" ] ; then
        echo "ℹ️ Keeping the user_agent BunkerBot in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's ignore_user_agent_urls set to http://blacklist-api:8080/user_agent ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT: "BunkerBot"@BLACKLIST_IGNORE_USER_AGENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS: ""@BLACKLIST_IGNORE_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@' {} \;
        else
            echo "🏴 Running tests with blacklist's ignore_user_agent_urls set to http://127.0.0.1:8080/user_agent ..."
            sudo sed -i 's@BLACKLIST_IGNORE_USER_AGENT=.*$@BLACKLIST_IGNORE_USER_AGENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS=.*$@BLACKLIST_IGNORE_USER_AGENT_URLS=http://127.0.0.1:8080/user_agent@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_USER_AGENT
            export BLACKLIST_IGNORE_USER_AGENT_URLS="http://127.0.0.1:8080/user_agent"
        fi
    elif [ "$test" = "user_agent_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's user_agent url set to http://blacklist-api:8080/user_agent ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@BLACKLIST_IGNORE_USER_AGENT_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT: "BunkerBot"@BLACKLIST_USER_AGENT: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT_URLS: ""@BLACKLIST_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@' {} \;
        else
            echo "🏴 Running tests with blacklist's user_agent url set to http://127.0.0.1:8080/user_agent ..."
            sudo sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS=.*$@BLACKLIST_IGNORE_USER_AGENT_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_USER_AGENT=.*$@BLACKLIST_USER_AGENT=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_USER_AGENT_URLS=.*$@BLACKLIST_USER_AGENT_URLS=http://127.0.0.1:8080/user_agent@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_USER_AGENT_URLS
            unset BLACKLIST_USER_AGENT
            export BLACKLIST_USER_AGENT_URLS="http://127.0.0.1:8080/user_agent"
        fi
    elif [ "$test" = "uri" ] ; then
        echo "🏴 Running tests with blacklist's uri set to /admin ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@BLACKLIST_USER_AGENT_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI: ""@BLACKLIST_URI: "/admin"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_USER_AGENT_URLS=.*$@BLACKLIST_USER_AGENT_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_URI=.*$@BLACKLIST_URI=/admin@' /etc/bunkerweb/variables.env
            unset BLACKLIST_USER_AGENT_URLS
            export BLACKLIST_URI="/admin"
        fi
    elif [ "$test" = "ignore_uri" ] ; then
        echo "🏴 Running tests with blacklist's ignore_uri set to /admin ..."
        echo "ℹ️ Keeping the uri /admin in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI: ""@BLACKLIST_IGNORE_URI: "/admin"@' {} \;
        else
            sudo sed -i 's@BLACKLIST_IGNORE_URI=.*$@BLACKLIST_IGNORE_URI=/admin@' /etc/bunkerweb/variables.env
            export BLACKLIST_IGNORE_URI="/admin"
        fi
    elif [ "$test" = "ignore_uri_urls" ] ; then
        echo "ℹ️ Keeping the uri /admin in the ban list ..."
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's ignore_ip_urls set to http://blacklist-api:8080/uri ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI: "/admin"@BLACKLIST_IGNORE_URI: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI_URLS: ""@BLACKLIST_IGNORE_URI_URLS: "http://blacklist-api:8080/uri"@' {} \;
        else
            echo "🏴 Running tests with blacklist's ignore_ip_urls set to http://127.0.0.1:8080/uri ..."
            sudo sed -i 's@BLACKLIST_IGNORE_URI=.*$@BLACKLIST_IGNORE_URI=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_IGNORE_URI_URLS=.*$@BLACKLIST_IGNORE_URI_URLS=http://127.0.0.1:8080/uri@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_URI
            export BLACKLIST_IGNORE_URI_URLS="http://127.0.0.1:8080/uri"
        fi
    elif [ "$test" = "uri_urls" ] ; then
        if [ "$integration" == "docker" ] ; then
            echo "🏴 Running tests with blacklist's uri url set to http://blacklist-api:8080/uri ..."
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI_URLS: "http://blacklist-api:8080/uri"@BLACKLIST_IGNORE_URI_URLS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI: "/admin"@BLACKLIST_URI: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI_URLS: ""@BLACKLIST_URI_URLS: "http://blacklist-api:8080/uri"@' {} \;
        else
            echo "🏴 Running tests with blacklist's uri url set to http://127.0.0.1:8080/uri ..."
            sudo sed -i 's@BLACKLIST_IGNORE_URI_URLS=.*$@BLACKLIST_IGNORE_URI_URLS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_URI=.*$@BLACKLIST_URI=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@BLACKLIST_URI_URLS=.*$@BLACKLIST_URI_URLS=http://127.0.0.1:8080/uri@' /etc/bunkerweb/variables.env
            unset BLACKLIST_IGNORE_URI_URLS
            unset BLACKLIST_URI
            export BLACKLIST_URI_URLS="http://127.0.0.1:8080/uri"
        fi
    fi

    echo "🏴 Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🏴 Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🏴 Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🏴 Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🏴 Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("blacklist-bw-1" "blacklist-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
                if [ "$check" = "" ] ; then
                    healthy="false"
                    break
                fi
            done
            if [ "$healthy" = "true" ] ; then
                echo "🏴 Docker stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge 120 ] ; then
            docker compose logs
            echo "🏴 Docker stack is not healthy ❌"
            exit 1
        fi
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🏴 Linux stack is healthy ✅"
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
                echo "🏴 Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🏴 ⚠ Linux stack got an issue, restarting ..."
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
            echo "🏴 Linux stack could not be healthy ❌"
            exit 1
        fi
    fi

    # Start tests


    if [ "$integration" == "docker" ] ; then
        if [[ "$test" = "asn" || "$test" = "ignore_asn" || "$test" = "ignore_asn_urls" || "$test" = "asn_urls" ]] ; then
            docker compose -f docker-compose.test.yml up global-tests --abort-on-container-exit --exit-code-from global-tests
        else
            docker compose -f docker-compose.test.yml up tests --abort-on-container-exit --exit-code-from tests
        fi
    else
        if [[ "$test" = "asn" || "$test" = "ignore_asn" || "$test" = "ignore_asn_urls" || "$test" = "asn_urls" ]] ; then
            export GLOBAL="yes"
        else
            unset GLOBAL
        fi
        python3 main.py
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🏴 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
        if [ "$integration" == "docker" ] ; then
            docker compose logs bw bw-scheduler blacklist-api
        else
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
        fi
        exit 1
    else
        echo "🏴 Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🏴 Tests are done ! ✅"
