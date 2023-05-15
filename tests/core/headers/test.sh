#!/bin/bash

echo "🎛️ Building headers stack ..."

# Starting stack
docker compose pull bw-docker bw-php
if [ $? -ne 0 ] ; then
    echo "🎛️ Pull failed ❌"
    exit 1
fi
docker compose -f docker-compose.test.yml build
if [ $? -ne 0 ] ; then
    echo "🎛️ Build failed ❌"
    exit 1
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CUSTOM_HEADER: "X-Test: test"@CUSTOM_HEADER: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REMOVE_HEADERS: ".*"$@REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@STRICT_TRANSPORT_SECURITY: "max-age=86400"@STRICT_TRANSPORT_SECURITY: "max-age=31536000"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_FLAGS: ".*"$@COOKIE_FLAGS: "* HttpOnly SameSite=Lax"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_AUTO_SECURE_FLAG: "no"@COOKIE_AUTO_SECURE_FLAG: "yes"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY: ".*"$@CONTENT_SECURITY_POLICY: "object-src '"'"'none'"'"'; form-action '"'"'self'"'"'; frame-ancestors '"'"'self'"'"';"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REFERRER_POLICY: "no-referrer"@REFERRER_POLICY: "strict-origin-when-cross-origin"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@PERMISSIONS_POLICY: ".*"$@PERMISSIONS_POLICY: "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), cross-origin-isolated=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), geolocation=(), gyroscope=(), hid=(), idle-detection=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), web-share=(), xr-spatial-tracking=()"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@FEATURE_POLICY: ".*"$@FEATURE_POLICY: "accelerometer '"'"'none'"'"'; ambient-light-sensor '"'"'none'"'"'; autoplay '"'"'none'"'"'; battery '"'"'none'"'"'; camera '"'"'none'"'"'; display-capture '"'"'none'"'"'; document-domain '"'"'none'"'"'; encrypted-media '"'"'none'"'"'; execution-while-not-rendered '"'"'none'"'"'; execution-while-out-of-viewport '"'"'none'"'"'; fullscreen '"'"'none'"'"'; geolocation '"'"'none'"'"'; gyroscope '"'"'none'"'"'; layout-animation '"'"'none'"'"'; legacy-image-formats '"'"'none'"'"'; magnetometer '"'"'none'"'"'; microphone '"'"'none'"'"'; midi '"'"'none'"'"'; navigation-override '"'"'none'"'"'; payment '"'"'none'"'"'; picture-in-picture '"'"'none'"'"'; publickey-credentials-get '"'"'none'"'"'; speaker-selection '"'"'none'"'"'; sync-xhr '"'"'none'"'"'; unoptimized-images '"'"'none'"'"'; unsized-media '"'"'none'"'"'; usb '"'"'none'"'"'; screen-wake-lock '"'"'none'"'"'; web-share '"'"'none'"'"'; xr-spatial-tracking '"'"'none'"'"';"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_FRAME_OPTIONS: "DENY"@X_FRAME_OPTIONS: "SAMEORIGIN"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_CONTENT_TYPE_OPTIONS: ""@X_CONTENT_TYPE_OPTIONS: "nosniff"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_XSS_PROTECTION: "0"@X_XSS_PROTECTION: "1; mode=block"@' {} \;

        if [[ $(sed '27!d' docker-compose.yml) = '      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' ]] ; then
            sed -i '27d' docker-compose.yml
        fi

        if [[ $(sed '13!d' docker-compose.test.yml) = '      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' ]] ; then
            sed -i '13d' docker-compose.test.yml
        fi

        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🎛️ Cleaning up current stack ..."

    docker compose down -v --remove-orphans 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🎛️ Down failed ❌"
        exit 1
    fi

    echo "🎛️ Cleaning up current stack done ✅"
}

# Cleanup stack on exit
trap cleanup_stack EXIT

for test in "without_ssl" "no_httponly_flag" "multiple_no_httponly_flag" "with_ssl" "no_cookie_auto_secure_flag"
do
    if [ "$test" = "without_ssl" ] ; then
        echo "🎛️ Running tests without ssl and with tweaked settings ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CUSTOM_HEADER: ""@CUSTOM_HEADER: "X-Test: test"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REMOVE_HEADERS: ".*"$@REMOVE_HEADERS: "X-Powered-By X-AspNet-Version X-AspNetMvc-Version"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@STRICT_TRANSPORT_SECURITY: "max-age=31536000"@STRICT_TRANSPORT_SECURITY: "max-age=86400"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY: ".*"$@CONTENT_SECURITY_POLICY: "object-src '"'"'none'"'"'; frame-ancestors '"'"'self'"'"';"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REFERRER_POLICY: "strict-origin-when-cross-origin"@REFERRER_POLICY: "no-referrer"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@PERMISSIONS_POLICY: ".*"$@PERMISSIONS_POLICY: "geolocation=(self), microphone=()"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@FEATURE_POLICY: ".*"$@FEATURE_POLICY: "geolocation '"'"'self'"'"'; microphone '"'"'none'"'"';"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_FRAME_OPTIONS: "SAMEORIGIN"@X_FRAME_OPTIONS: "DENY"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_CONTENT_TYPE_OPTIONS: "nosniff"@X_CONTENT_TYPE_OPTIONS: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_XSS_PROTECTION: "1; mode=block"@X_XSS_PROTECTION: "0"@' {} \;
    elif [ "$test" = "no_httponly_flag" ] ; then
        echo "🎛️ Running tests without HttpOnly flag for cookies and with default values ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_FLAGS: ".*"$@COOKIE_FLAGS: "* SameSite=Lax"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CUSTOM_HEADER: "X-Test: test"@CUSTOM_HEADER: ""@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REMOVE_HEADERS: ".*"$@REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@STRICT_TRANSPORT_SECURITY: "max-age=86400"@STRICT_TRANSPORT_SECURITY: "max-age=31536000"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY: ".*"$@CONTENT_SECURITY_POLICY: "object-src '"'"'none'"'"'; form-action '"'"'self'"'"'; frame-ancestors '"'"'self'"'"';"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@REFERRER_POLICY: "no-referrer"@REFERRER_POLICY: "strict-origin-when-cross-origin"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@PERMISSIONS_POLICY: ".*"$@PERMISSIONS_POLICY: "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), cross-origin-isolated=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), geolocation=(), gyroscope=(), hid=(), idle-detection=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), web-share=(), xr-spatial-tracking=()"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@FEATURE_POLICY: ".*"$@FEATURE_POLICY: "accelerometer '"'"'none'"'"'; ambient-light-sensor '"'"'none'"'"'; autoplay '"'"'none'"'"'; battery '"'"'none'"'"'; camera '"'"'none'"'"'; display-capture '"'"'none'"'"'; document-domain '"'"'none'"'"'; encrypted-media '"'"'none'"'"'; execution-while-not-rendered '"'"'none'"'"'; execution-while-out-of-viewport '"'"'none'"'"'; fullscreen '"'"'none'"'"'; geolocation '"'"'none'"'"'; gyroscope '"'"'none'"'"'; layout-animation '"'"'none'"'"'; legacy-image-formats '"'"'none'"'"'; magnetometer '"'"'none'"'"'; microphone '"'"'none'"'"'; midi '"'"'none'"'"'; navigation-override '"'"'none'"'"'; payment '"'"'none'"'"'; picture-in-picture '"'"'none'"'"'; publickey-credentials-get '"'"'none'"'"'; speaker-selection '"'"'none'"'"'; sync-xhr '"'"'none'"'"'; unoptimized-images '"'"'none'"'"'; unsized-media '"'"'none'"'"'; usb '"'"'none'"'"'; screen-wake-lock '"'"'none'"'"'; web-share '"'"'none'"'"'; xr-spatial-tracking '"'"'none'"'"';"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_FRAME_OPTIONS: "DENY"@X_FRAME_OPTIONS: "SAMEORIGIN"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_CONTENT_TYPE_OPTIONS: ""@X_CONTENT_TYPE_OPTIONS: "nosniff"@' {} \;
        find . -type f -name 'docker-compose.*' -exec sed -i 's@X_XSS_PROTECTION: "0"@X_XSS_PROTECTION: "1; mode=block"@' {} \;
    elif [ "$test" = "multiple_no_httponly_flag" ] ; then
        echo "🎛️ Running tests with HttpOnly flag overriden for cookie \"bw_cookie\" and default cookies flags ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_FLAGS: ".*"$@COOKIE_FLAGS: "* HttpOnly SameSite=Lax"@' {} \;
        sed -i '27i \      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' docker-compose.yml
        sed -i '13i \      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' docker-compose.test.yml
    elif [ "$test" = "with_ssl" ] ; then
        echo "🎛️ Running tests with ssl ..."
        find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
        sed -i '27d' docker-compose.yml
        sed -i '13d' docker-compose.test.yml
    elif [ "$test" = "no_cookie_auto_secure_flag" ] ; then
        echo "🎛️ Running tests without cookie_auto_secure_flag ..."
        echo "ℹ️ Keeping the generated self-signed SSL certificate"
        find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_AUTO_SECURE_FLAG: "yes"@COOKIE_AUTO_SECURE_FLAG: "no"@' {} \;
    fi

    echo "🎛️ Starting stack ..."
    docker compose up -d 2>/dev/null
    if [ $? -ne 0 ] ; then
        echo "🎛️ Up failed, retrying ... ⚠️"
        manual=1
        cleanup_stack
        manual=0
        docker compose up -d 2>/dev/null
        if [ $? -ne 0 ] ; then
            echo "🎛️ Up failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🎛️ Waiting for stack to be healthy ..."
    i=0
    while [ $i -lt 120 ] ; do
        containers=("headers-bw-1" "headers-bw-scheduler-1")
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" $container | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            echo "🎛️ Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge 120 ] ; then
        docker compose logs
        echo "🎛️ Docker stack is not healthy ❌"
        exit 1
    fi

    # Start tests

    docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from tests 2>/dev/null

    if [ $? -ne 0 ] ; then
        echo "🎛️ Test \"$test\" failed ❌"
        echo "🛡️ Showing BunkerWeb and BunkerWeb Scheduler logs ..."
        docker compose logs bw bw-scheduler
        exit 1
    else
        echo "🎛️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🎛️ Tests are done ! ✅"
