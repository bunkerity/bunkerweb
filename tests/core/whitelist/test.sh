#!/bin/bash

echo "🏳️ Building whitelist stack ..."

# Starting stack
docker compose pull bw-docker
if [ $? -ne 0 ] ; then
    echo "🏳️ Pull failed ❌"
    exit 1
fi

echo "🏳️ Building custom api image ..."
docker compose build whitelist-api
if [ $? -ne 0 ] ; then
    echo "🏳️ Build failed ❌"
    exit 1
fi

echo "🏳️ Building tests images ..."
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🏳️ Build failed ❌"
    exit 1
fi

manual=0
end=0
as_number=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        rm -rf init/output
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_WHITELIST: "yes"@USE_WHITELIST: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_IP: "192.168.0.0/24"@WHITELIST_IP: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_IP_URLS: "http://whitelist-api:8080/ip"@WHITELIST_IP_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS_GLOBAL: "no"@WHITELIST_RDNS_GLOBAL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS: ".bw-services"@WHITELIST_RDNS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS_URLS: "http://whitelist-api:8080/rdns"@WHITELIST_RDNS_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_ASN: "[0-9]*"@WHITELIST_ASN: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_ASN_URLS: "http://whitelist-api:8080/asn"@WHITELIST_ASN_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_USER_AGENT: "BunkerBot"@WHITELIST_USER_AGENT: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_USER_AGENT_URLS: "http://whitelist-api:8080/user_agent"@WHITELIST_USER_AGENT_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_URI: "/admin"@WHITELIST_URI: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_URI_URLS: "http://whitelist-api:8080/uri"@WHITELIST_URI_URLS: ""@' {} \;
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🏳️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans

    if [ $? -ne 0 ] ; then
        echo "🏳️ Down failed ❌"
        exit 1
    fi

    echo "🏳️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

echo "🏳️ Initializing workspace ..."
rm -rf init/output
mkdir -p init/output
docker compose -f docker-compose.init.yml up --build
if [ $? -ne 0 ] ; then
    echo "🏳️ Build failed ❌"
    exit 1
elif ! [[ -f "init/output/ip_asn.txt" ]]; then
    echo "🏳️ ip_asn.txt not found ❌"
    exit 1
fi

as_number=$(cat init/output/ip_asn.txt)

if [[ $as_number = "" ]]; then
    echo "🏳️ AS number not found ❌"
    exit 1
fi

rm -rf init/output

for test in "deactivated" "ip" "ip_urls" "rdns" "rdns_global" "rdns_urls" "asn" "asn_urls" "user_agent" "user_agent_urls" "uri" "uri_urls"
do
    if [ "$test" = "deactivated" ] ; then
        echo "🏳️ Running tests when the whitelist is deactivated ..."
        echo "ℹ️ Activating the blacklist and banning 0.0.0.0/0 network for all the future tests ..."
    elif [ "$test" = "ip" ] ; then
        echo "🏳️ Running tests with the network 192.168.0.0/24 in the white list ..."
        echo "ℹ️ Activating the whitelist for all the future tests ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@USE_WHITELIST: "no"@USE_WHITELIST: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_IP: ""@WHITELIST_IP: "192.168.0.0/24"@' {} \;
    elif [ "$test" = "ip_urls" ] ; then
        echo "🏳️ Running tests with whitelist's ip url set to http://whitelist-api:8080/ip ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_IP: "192.168.0.0/24"@WHITELIST_IP: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_IP_URLS: ""@WHITELIST_IP_URLS: "http://whitelist-api:8080/ip"@' {} \;
    elif [ "$test" = "rdns" ] ; then
        echo "🏳️ Running tests with whitelist's rdns set to .bw-services ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_IP_URLS: "http://whitelist-api:8080/ip"@WHITELIST_IP_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS: ""@WHITELIST_RDNS: ".bw-services"@' {} \;
    elif [ "$test" = "rdns_global" ] ; then
        echo "🏳️ Running tests when whitelist's rdns also scans local ip addresses ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS_GLOBAL: "yes"@WHITELIST_RDNS_GLOBAL: "no"@' {} \;
    elif [ "$test" = "rdns_urls" ] ; then
        echo "🏳️ Running tests with whitelist's rdns url set to http://whitelist-api:8080/rdns ..."
        echo "ℹ️ Keeping the rdns also scanning local ip addresses ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS: ".bw-services"@WHITELIST_RDNS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS_URLS: ""@WHITELIST_RDNS_URLS: "http://whitelist-api:8080/rdns"@' {} \;
    elif [ "$test" = "asn" ] ; then
        echo "🏳️ Running tests with whitelist's asn set to $as_number ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS_GLOBAL: "no"@WHITELIST_RDNS_GLOBAL: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_RDNS_URLS: "http://whitelist-api:8080/rdns"@WHITELIST_RDNS_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_ASN: ""@WHITELIST_ASN: "'"$as_number"'"@' {} \;
    elif [ "$test" = "asn_urls" ] ; then
        echo "🏳️ Running tests with whitelist's asn url set to http://whitelist-api:8080/asn ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_ASN: "'"$as_number"'"@WHITELIST_ASN: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_ASN_URLS: ""@WHITELIST_ASN_URLS: "http://whitelist-api:8080/asn"@' {} \;
    elif [ "$test" = "user_agent" ] ; then
        echo "🏳️ Running tests with whitelist's user_agent set to BunkerBot ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_ASN_URLS: "http://whitelist-api:8080/asn"@WHITELIST_ASN_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_USER_AGENT: ""@WHITELIST_USER_AGENT: "BunkerBot"@' {} \;
    elif [ "$test" = "user_agent_urls" ] ; then
        echo "🏳️ Running tests with whitelist's user_agent url set to http://whitelist-api:8080/user_agent ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_USER_AGENT: "BunkerBot"@WHITELIST_USER_AGENT: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_USER_AGENT_URLS: ""@WHITELIST_USER_AGENT_URLS: "http://whitelist-api:8080/user_agent"@' {} \;
    elif [ "$test" = "uri" ] ; then
        echo "🏳️ Running tests with whitelist's uri set to /admin ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_USER_AGENT_URLS: "http://whitelist-api:8080/user_agent"@WHITELIST_USER_AGENT_URLS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_URI: ""@WHITELIST_URI: "/admin"@' {} \;
    elif [ "$test" = "uri_urls" ] ; then
        echo "🏳️ Running tests with whitelist's uri url set to http://whitelist-api:8080/uri ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_URI: "/admin"@WHITELIST_URI: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@WHITELIST_URI_URLS: ""@WHITELIST_URI_URLS: "http://whitelist-api:8080/uri"@' {} \;
    fi

    echo "🏳️ Starting stack ..."
    docker compose up -d
    if [ $? -ne 0 ] ; then
        echo "🏳️ Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d
        if [ $? -ne 0 ] ; then
            echo "🏳️ Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🏳️ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("whitelist-bw-1" "whitelist-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🏳️ Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🏳️ Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    if ! [[ "$test" = "user_agent" || "$test" = "user_agent_urls" || "$test" = "uri" || "$test" = "uri_urls" ]] ; then
        echo "🏳️ Running global container tests ..."

        docker compose -f docker-compose.test.yml up global-tests --abort-on-container-exit --exit-code-from global-tests

        if [ $? -ne 0 ] ; then
            echo "🏳️ Test \"$test\" failed for global tests ❌"
            echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
            docker compose logs bw bw-scheduler whitelist-api
            exit 1
        else
            echo "🏳️ Test \"$test\" succeeded for global tests ✅"
        fi
    fi

    echo "🏳️ Running local container tests ..."

    docker compose -f docker-compose.test.yml up local-tests --abort-on-container-exit --exit-code-from local-tests

    if [ $? -ne 0 ] ; then
        echo "🏳️ Test \"$test\" failed for local tests ❌"
        echo "🛡️ Showing BunkerWeb, BunkerWeb Scheduler and Custom API logs ..."
        docker compose logs bw bw-scheduler whitelist-api
        exit 1
    else
        echo "🏳️ Test \"$test\" succeeded for local tests ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🏳️ Tests are done ! ✅"
