#!/bin/bash

echo "🏴 Building blacklist stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🏴 Pull failed ❌"
    exit 1
fi

echo "🏴 Building custom api image ..."
docker compose build blacklist-api
if [ $? -ne 0 ] ; then
    echo "🏴 Build failed ❌"
    exit 1
fi

echo "🏴 Building tests images ..."
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🏴 Build failed ❌"
    exit 1
fi

manual=0
end=0
as_number=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
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
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🏴 Cleaning up current stack ..."

    docker compose down -v --remove-orphans

    if [ $? -ne 0 ] ; then
        echo "🏴 Down failed ❌"
        exit 1
    fi

    echo "🏴 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🏴 Initializing workspace ..."
rm -rf init/output
mkdir -p init/output
docker compose -f docker-compose.init.yml up --build
if [ $? -ne 0 ] ; then
    echo "🏴 Build failed ❌"
    exit 1
elif ! [[ -f "init/output/ip_asn.txt" ]]; then
    echo "🏴 ip_asn.txt not found ❌"
    exit 1
fi

as_number=$(cat init/output/ip_asn.txt)

if [[ $as_number = "" ]]; then
    echo "🏴 AS number not found ❌"
    exit 1
fi

rm -rf init/output

for test in "ip" "deactivated" "ignore_ip" "ignore_ip_urls" "ip_urls" "rdns" "rdns_global" "ignore_rdns" "ignore_rdns_urls" "rdns_urls" "asn" "ignore_asn" "ignore_asn_urls" "asn_urls" "user_agent" "ignore_user_agent" "ignore_user_agent_urls" "user_agent_urls" "uri" "ignore_uri" "ignore_uri_urls" "uri_urls"
do
    if [ "$test" = "ip" ] ; then
        echo "🏴 Running tests with the network 0.0.0.0/0 in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP: ""@BLACKLIST_IP: "0.0.0.0/0"@' {} \;
    elif [ "$test" = "deactivated" ] ; then
        echo "🏴 Running tests when deactivating the blacklist ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BLACKLIST: "yes"@USE_BLACKLIST: "no"@' {} \;
    elif [ "$test" = "ignore_ip" ] ; then
        echo "🏴 Running tests with blacklist's ignore_ip set to 192.168.0.3 ..."
        echo "ℹ️ Keeping the network 0.0.0.0/0 in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_BLACKLIST: "no"@USE_BLACKLIST: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP: ""@BLACKLIST_IGNORE_IP: "192.168.0.3"@' {} \;
    elif [ "$test" = "ignore_ip_urls" ] ; then
        echo "🏴 Running tests with blacklist's ignore_ip_urls set to http://blacklist-api:8080/ip ..."
        echo "ℹ️ Keeping the network 0.0.0.0/0 in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP: "192.168.0.3"@BLACKLIST_IGNORE_IP: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP_URLS: ""@BLACKLIST_IGNORE_IP_URLS: "http://blacklist-api:8080/ip"@' {} \;
    elif [ "$test" = "ip_urls" ] ; then
        echo "🏴 Running tests with blacklist's ip url set to http://blacklist-api:8080/ip ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_IP_URLS: "http://blacklist-api:8080/ip"@BLACKLIST_IGNORE_IP_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP: "0.0.0.0/0"@BLACKLIST_IP: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IP_URLS: ""@BLACKLIST_IP_URLS: "http://blacklist-api:8080/ip"@' {} \;
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
        echo "🏴 Running tests with blacklist's asn set to $as_number ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_GLOBAL: "no"@BLACKLIST_RDNS_GLOBAL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_RDNS_URLS: "http://blacklist-api:8080/rdns"@BLACKLIST_RDNS_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN: ""@BLACKLIST_ASN: "'"$as_number"'"@' {} \;
    elif [ "$test" = "ignore_asn" ] ; then
        echo "🏴 Running tests with blacklist's ignore_asn set to $as_number ..."
        echo "ℹ️ Keeping the asn $as_number in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN: ""@BLACKLIST_IGNORE_ASN: "'"$as_number"'"@' {} \;
    elif [ "$test" = "ignore_asn_urls" ] ; then
        echo "🏴 Running tests with blacklist's ignore_asn_urls set to http://blacklist-api:8080/asn ..."
        echo "ℹ️ Keeping the asn $as_number in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN: "'"$as_number"'"@BLACKLIST_IGNORE_ASN: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN_URLS: ""@BLACKLIST_IGNORE_ASN_URLS: "http://blacklist-api:8080/asn"@' {} \;
    elif [ "$test" = "asn_urls" ] ; then
        echo "🏴 Running tests with blacklist's asn url set to http://blacklist-api:8080/asn ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_ASN_URLS: "http://blacklist-api:8080/asn"@BLACKLIST_IGNORE_ASN_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN: "'"$as_number"'"@BLACKLIST_ASN: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN_URLS: ""@BLACKLIST_ASN_URLS: "http://blacklist-api:8080/asn"@' {} \;
    elif [ "$test" = "user_agent" ] ; then
        echo "🏴 Running tests with blacklist's user_agent set to BunkerBot ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_ASN_URLS: "http://blacklist-api:8080/asn"@BLACKLIST_ASN_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT: ""@BLACKLIST_USER_AGENT: "BunkerBot"@' {} \;
    elif [ "$test" = "ignore_user_agent" ] ; then
        echo "🏴 Running tests with blacklist's ignore_user_agent set to BunkerBot ..."
        echo "ℹ️ Keeping the user_agent BunkerBot in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT: ""@BLACKLIST_IGNORE_USER_AGENT: "BunkerBot"@' {} \;
    elif [ "$test" = "ignore_user_agent_urls" ] ; then
        echo "🏴 Running tests with blacklist's ignore_user_agent_urls set to http://blacklist-api:8080/user_agent ..."
        echo "ℹ️ Keeping the user_agent BunkerBot in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT: "BunkerBot"@BLACKLIST_IGNORE_USER_AGENT: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS: ""@BLACKLIST_IGNORE_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@' {} \;
    elif [ "$test" = "user_agent_urls" ] ; then
        echo "🏴 Running tests with blacklist's user_agent url set to http://blacklist-api:8080/user_agent ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@BLACKLIST_IGNORE_USER_AGENT_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT: "BunkerBot"@BLACKLIST_USER_AGENT: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT_URLS: ""@BLACKLIST_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@' {} \;
    elif [ "$test" = "uri" ] ; then
        echo "🏴 Running tests with blacklist's uri set to /admin ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_USER_AGENT_URLS: "http://blacklist-api:8080/user_agent"@BLACKLIST_USER_AGENT_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI: ""@BLACKLIST_URI: "/admin"@' {} \;
    elif [ "$test" = "ignore_uri" ] ; then
        echo "🏴 Running tests with blacklist's ignore_uri set to /admin ..."
        echo "ℹ️ Keeping the uri /admin in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI: ""@BLACKLIST_IGNORE_URI: "/admin"@' {} \;
    elif [ "$test" = "ignore_uri_urls" ] ; then
        echo "🏴 Running tests with blacklist's ignore_ip_urls set to http://blacklist-api:8080/uri ..."
        echo "ℹ️ Keeping the uri /admin in the ban list ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI: "/admin"@BLACKLIST_IGNORE_URI: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI_URLS: ""@BLACKLIST_IGNORE_URI_URLS: "http://blacklist-api:8080/uri"@' {} \;
    elif [ "$test" = "uri_urls" ] ; then
        echo "🏴 Running tests with blacklist's uri url set to http://blacklist-api:8080/uri ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_IGNORE_URI_URLS: "http://blacklist-api:8080/uri"@BLACKLIST_IGNORE_URI_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI: "/admin"@BLACKLIST_URI: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@BLACKLIST_URI_URLS: ""@BLACKLIST_URI_URLS: "http://blacklist-api:8080/uri"@' {} \;
    fi

    echo "🏴 Starting stack ..."
    docker compose up -d
    if [ $? -ne 0 ] ; then
        echo "🏴 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🏴 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🏴 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("blacklist-bw-1" "blacklist-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
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

    # Start tests

    if [[ "$test" = "asn" || "$test" = "ignore_asn" || "$test" = "ignore_asn_urls" || "$test" = "asn_urls" ]] ; then
        docker compose -f docker-compose.test.yml up global-tests --abort-on-container-exit --exit-code-from global-tests
    else
        docker compose -f docker-compose.test.yml up tests --abort-on-container-exit --exit-code-from tests
    fi

    if [ $? -ne 0 ] ; then
        echo "🏴 Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
        docker compose logs bw bw-scheduler blacklist-api
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
