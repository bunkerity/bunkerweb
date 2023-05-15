#!/bin/bash

echo "🏁 Building greylist stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🏁 Pull failed ❌"
    exit 1
fi

echo "🏁 Building custom api image ..."
docker compose build greylist-api
if [ $? -ne 0 ] ; then
    echo "🏁 Build failed ❌"
    exit 1
fi

echo "🏁 Building tests images ..."
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🏁 Build failed ❌"
    exit 1
fi

manual=0
end=0
as_number=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
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
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🏁 Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🏁 Down failed ❌"
        exit 1
    fi

    echo "🏁 Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🏁 Initializing workspace ..."
rm -rf init/output
mkdir -p init/output
docker compose -f docker-compose.init.yml up --build
if [ $? -ne 0 ] ; then
    echo "🏁 Build failed ❌"
    exit 1
elif ! [[ -f "init/output/ip_asn.txt" ]]; then
    echo "🏁 ip_asn.txt not found ❌"
    exit 1
fi

as_number=$(cat init/output/ip_asn.txt)

if [[ $as_number = "" ]]; then
    echo "🏁 AS number not found ❌"
    exit 1
fi

rm -rf init/output

for test in "deactivated" "ip" "ip_urls" "rdns" "rdns_global" "rdns_urls" "asn" "asn_urls" "user_agent" "user_agent_urls" "uri" "uri_urls"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🏁 Running tests when the greylist is deactivated ..."
    elif [ "$test" = "ip" ] ; then
        echo "🏁 Running tests with the network 192.168.0.0/24 in the grey list ..."
        echo "ℹ️ Activating the greylist for all the future tests ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_GREYLIST: "no"@USE_GREYLIST: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP: ""@GREYLIST_IP: "192.168.0.0/24"@' {} \;
    elif [ "$test" = "ip_urls" ] ; then
        echo "🏁 Running tests with greylist's ip url set to http://greylist-api:8080/ip ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP: "192.168.0.0/24"@GREYLIST_IP: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_IP_URLS: ""@GREYLIST_IP_URLS: "http://greylist-api:8080/ip"@' {} \;
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
        echo "🏁 Running tests with greylist's asn set to $as_number ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_GLOBAL: "no"@GREYLIST_RDNS_GLOBAL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_RDNS_URLS: "http://greylist-api:8080/rdns"@GREYLIST_RDNS_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN: ""@GREYLIST_ASN: "'"$as_number"'"@' {} \;
    elif [ "$test" = "asn_urls" ] ; then
        echo "🏁 Running tests with greylist's asn url set to http://greylist-api:8080/asn ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN: "'"$as_number"'"@GREYLIST_ASN: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN_URLS: ""@GREYLIST_ASN_URLS: "http://greylist-api:8080/asn"@' {} \;
    elif [ "$test" = "user_agent" ] ; then
        echo "🏁 Running tests with greylist's user_agent set to BunkerBot ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_ASN_URLS: "http://greylist-api:8080/asn"@GREYLIST_ASN_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT: ""@GREYLIST_USER_AGENT: "BunkerBot"@' {} \;
    elif [ "$test" = "user_agent_urls" ] ; then
        echo "🏁 Running tests with greylist's user_agent url set to http://greylist-api:8080/user_agent ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT: "BunkerBot"@GREYLIST_USER_AGENT: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT_URLS: ""@GREYLIST_USER_AGENT_URLS: "http://greylist-api:8080/user_agent"@' {} \;
    elif [ "$test" = "uri" ] ; then
        echo "🏁 Running tests with greylist's uri set to /admin ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_USER_AGENT_URLS: "http://greylist-api:8080/user_agent"@GREYLIST_USER_AGENT_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI: ""@GREYLIST_URI: "/admin"@' {} \;
    elif [ "$test" = "uri_urls" ] ; then
        echo "🏁 Running tests with greylist's uri url set to http://greylist-api:8080/uri ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI: "/admin"@GREYLIST_URI: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GREYLIST_URI_URLS: ""@GREYLIST_URI_URLS: "http://greylist-api:8080/uri"@' {} \;
    fi

    echo "🏁 Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🏁 Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        if [ $? -ne 0 ] ; then
            echo "🏁 Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🏁 Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("greylist-bw-1" "greylist-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
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

    # Start tests

    if ! [[ "$test" = "user_agent" || "$test" = "user_agent_urls" || "$test" = "uri" || "$test" = "uri_urls" ]] ; then
        echo "🏁 Running global container tests ..."

        docker compose -f docker-compose.test.yml up global-tests --abort-on-container-exit --exit-code-from global-tests 2>/dev/null

        if [ $? -ne 0 ] ; then
            echo "🏁 Test \"$test\" failed for global tests ❌"
            echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
            docker compose logs bw bw-scheduler greylist-api
            exit 1
        else
            echo "🏁 Test \"$test\" succeeded for global tests ✅"
        fi
    fi

    echo "🏁 Running local container tests ..."

    docker compose -f docker-compose.test.yml up local-tests --abort-on-container-exit --exit-code-from local-tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🏁 Test \"$test\" failed for local tests ❌"
        echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
        docker compose logs bw bw-scheduler greylist-api
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
