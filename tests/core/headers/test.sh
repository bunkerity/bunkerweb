#!/bin/bash

integration=$1

if [ -z "$integration" ] ; then
    echo "🎛️ Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "docker" ] && [ "$integration" != "linux" ] ; then
    echo "🎛️ Integration \"$integration\" is not supported ❌"
    exit 1
fi

echo "🎛️ Building headers stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "docker" ] ; then
    docker compose pull bw-php
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🎛️ Pull failed ❌"
        exit 1
    fi
    docker compose -f docker-compose.test.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🎛️ Build failed ❌"
        exit 1
    fi
else
    sudo systemctl stop bunkerweb
    sudo cp -r www/* /var/www/html/
    sudo chown -R www-data:nginx /var/www/html
    sudo find /var/www/html -type f -exec chmod 0640 {} \;
    sudo find /var/www/html -type d -exec chmod 0750 {} \;
    echo "LOCAL_PHP=/run/php/php-fpm.sock" | sudo tee -a /etc/bunkerweb/variables.env
    echo "LOCAL_PHP_PATH=/var/www/html" | sudo tee -a /etc/bunkerweb/variables.env
    echo "GENERATE_SELF_SIGNED_SSL=no" | sudo tee -a /etc/bunkerweb/variables.env

    echo "CUSTOM_HEADER=" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REMOVE_HEADERS=Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version" | sudo tee -a /etc/bunkerweb/variables.env
    echo "KEEP_UPSTREAM_HEADERS=Content-Security-Policy X-Frame-Options" | sudo tee -a /etc/bunkerweb/variables.env
    echo "STRICT_TRANSPORT_SECURITY=max-age=31536000; includeSubDomains; preload" | sudo tee -a /etc/bunkerweb/variables.env
    echo "COOKIE_FLAGS=* HttpOnly SameSite=Lax" | sudo tee -a /etc/bunkerweb/variables.env
    echo "COOKIE_AUTO_SECURE_FLAG=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CONTENT_SECURITY_POLICY=object-src 'none'; form-action 'self'; frame-ancestors 'self';" | sudo tee -a /etc/bunkerweb/variables.env
    echo "CONTENT_SECURITY_POLICY_REPORT_ONLY=no" | sudo tee -a /etc/bunkerweb/variables.env
    echo "REFERRER_POLICY=strict-origin-when-cross-origin" | sudo tee -a /etc/bunkerweb/variables.env
    echo "PERMISSIONS_POLICY=accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=()" | sudo tee -a /etc/bunkerweb/variables.env
    echo "DISABLE_FLOC=yes" | sudo tee -a /etc/bunkerweb/variables.env
    echo "X_FRAME_OPTIONS=SAMEORIGIN" | sudo tee -a /etc/bunkerweb/variables.env
    echo "X_CONTENT_TYPE_OPTIONS=nosniff" | sudo tee -a /etc/bunkerweb/variables.env
    echo "X_XSS_PROTECTION=1; mode=block" | sudo tee -a /etc/bunkerweb/variables.env
    echo "X_DNS_PREFETCH_CONTROL=off" | sudo tee -a /etc/bunkerweb/variables.env
    sudo cp ready.conf /etc/bunkerweb/configs/server-http
fi

manual=0
end=0
cleanup_stack () {
    exit_code=$?
    if [[ $end -eq 1 || $exit_code = 1 ]] || [[ $end -eq 0 && $exit_code = 0 ]] && [ $manual = 0 ] ; then
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CUSTOM_HEADER: "X-Test: test"@CUSTOM_HEADER: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REMOVE_HEADERS: ".*"$@REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@KEEP_UPSTREAM_HEADERS: ".*"$@KEEP_UPSTREAM_HEADERS: "Content-Security-Policy X-Frame-Options"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@STRICT_TRANSPORT_SECURITY: "max-age=86400"@STRICT_TRANSPORT_SECURITY: "max-age=31536000; includeSubDomains; preload"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_FLAGS: ".*"$@COOKIE_FLAGS: "* HttpOnly SameSite=Lax"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_AUTO_SECURE_FLAG: "no"@COOKIE_AUTO_SECURE_FLAG: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY: ".*"$@CONTENT_SECURITY_POLICY: "object-src '"'"'none'"'"'; form-action '"'"'self'"'"'; frame-ancestors '"'"'self'"'"';"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY_REPORT_ONLY: ".*"$@CONTENT_SECURITY_POLICY_REPORT_ONLY: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REFERRER_POLICY: "no-referrer"@REFERRER_POLICY: "strict-origin-when-cross-origin"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@PERMISSIONS_POLICY: ".*"$@PERMISSIONS_POLICY: "accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=()"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_FLOC: ".*"@DISABLE_FLOC: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_FRAME_OPTIONS: "DENY"@X_FRAME_OPTIONS: "SAMEORIGIN"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_CONTENT_TYPE_OPTIONS: ""@X_CONTENT_TYPE_OPTIONS: "nosniff"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_XSS_PROTECTION: "0"@X_XSS_PROTECTION: "1; mode=block"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_DNS_PREFETCH_CONTROL: ".*"@X_DNS_PREFETCH_CONTROL: "off"@' {} \;

            if [[ $(sed '27!d' docker-compose.yml) = '      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' ]] ; then
                sed -i '27d' docker-compose.yml
            fi

            if [[ $(sed '13!d' docker-compose.test.yml) = '      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' ]] ; then
                sed -i '13d' docker-compose.test.yml
            fi
        else
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CUSTOM_HEADER=.*$@CUSTOM_HEADER=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REMOVE_HEADERS=.*$@REMOVE_HEADERS=Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version@' /etc/bunkerweb/variables.env
            sudo sed -i 's@KEEP_UPSTREAM_HEADERS=.*$@KEEP_UPSTREAM_HEADERS=Content-Security-Policy X-Frame-Options@' /etc/bunkerweb/variables.env
            sudo sed -i 's@STRICT_TRANSPORT_SECURITY=.*$@STRICT_TRANSPORT_SECURITY=max-age=31536000; includeSubDomains; preload@' /etc/bunkerweb/variables.env
            sudo sed -i 's@COOKIE_FLAGS=.*$@COOKIE_FLAGS=* HttpOnly SameSite=Lax@' /etc/bunkerweb/variables.env
            sudo sed -i 's@COOKIE_AUTO_SECURE_FLAG=.*$@COOKIE_AUTO_SECURE_FLAG=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CONTENT_SECURITY_POLICY=.*$@CONTENT_SECURITY_POLICY=object-src '"'"'none'"'"'; form-action '"'"'self'"'"'; frame-ancestors '"'"'self'"'"';@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CONTENT_SECURITY_POLICY_REPORT_ONLY=.*$@CONTENT_SECURITY_POLICY_REPORT_ONLY=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REFERRER_POLICY=.*$@REFERRER_POLICY=strict-origin-when-cross-origin@' /etc/bunkerweb/variables.env
            sudo sed -i 's@PERMISSIONS_POLICY=.*$@PERMISSIONS_POLICY=accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=()@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DISABLE_FLOC=.*$@DISABLE_FLOC=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_FRAME_OPTIONS=.*$@X_FRAME_OPTIONS=SAMEORIGIN@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_CONTENT_TYPE_OPTIONS=.*$@X_CONTENT_TYPE_OPTIONS=nosniff@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_XSS_PROTECTION=.*$@X_XSS_PROTECTION=1; mode=block@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_DNS_PREFETCH_CONTROL=.*$@X_DNS_PREFETCH_CONTROL=off@' /etc/bunkerweb/variables.env
            unset GENERATE_SELF_SIGNED_SSL
            unset CUSTOM_HEADER
            unset REMOVE_HEADERS
            unset KEEP_UPSTREAM_HEADERS
            unset STRICT_TRANSPORT_SECURITY
            unset COOKIE_FLAGS
            unset COOKIE_AUTO_SECURE_FLAG
            unset CONTENT_SECURITY_POLICY
            unset CONTENT_SECURITY_POLICY_REPORT_ONLY
            unset REFERRER_POLICY
            unset PERMISSIONS_POLICY
            unset DISABLE_FLOC
            unset X_FRAME_OPTIONS
            unset X_CONTENT_TYPE_OPTIONS
            unset X_XSS_PROTECTION
            unset X_DNS_PREFETCH_CONTROL

            if [[ $(sudo tail -n 1 /etc/bunkerweb/variables.env) = 'COOKIE_FLAGS_1=bw_cookie SameSite=Lax' ]] ; then
                sudo sed -i '$ d' /etc/bunkerweb/variables.env
            fi
            unset COOKIE_FLAGS_1
        fi
        if [[ $end -eq 1 && $exit_code = 0 ]] ; then
            return
        fi
    fi

    echo "🎛️ Cleaning up current stack ..."

    if [ "$integration" == "docker" ] ; then
        docker compose down -v --remove-orphans
    else
        sudo systemctl stop bunkerweb
        sudo truncate -s 0 /var/log/bunkerweb/error.log
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "🎛️ Cleanup failed ❌"
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
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CUSTOM_HEADER: ""@CUSTOM_HEADER: "X-Test: test"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REMOVE_HEADERS: ".*"$@REMOVE_HEADERS: "X-Powered-By X-AspNet-Version X-AspNetMvc-Version"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@STRICT_TRANSPORT_SECURITY: "max-age=31536000; includeSubDomains; preload"@STRICT_TRANSPORT_SECURITY: "max-age=86400"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY: ".*"$@CONTENT_SECURITY_POLICY: "object-src '"'"'none'"'"'; frame-ancestors '"'"'self'"'"';"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY_REPORT_ONLY: "no"@CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REFERRER_POLICY: "strict-origin-when-cross-origin"@REFERRER_POLICY: "no-referrer"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@PERMISSIONS_POLICY: ".*"$@PERMISSIONS_POLICY: "geolocation=(self), microphone=()"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_FLOC: "yes"@DISABLE_FLOC: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_FRAME_OPTIONS: "SAMEORIGIN"@X_FRAME_OPTIONS: "DENY"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_CONTENT_TYPE_OPTIONS: "nosniff"@X_CONTENT_TYPE_OPTIONS: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_XSS_PROTECTION: "1; mode=block"@X_XSS_PROTECTION: "0"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_DNS_PREFETCH_CONTROL: "off"@X_DNS_PREFETCH_CONTROL: "on"@' {} \;
        else
            sudo sed -i 's@CUSTOM_HEADER=.*$@CUSTOM_HEADER=X-Test: test@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REMOVE_HEADERS=.*$@REMOVE_HEADERS=X-Powered-By X-AspNet-Version X-AspNetMvc-Version@' /etc/bunkerweb/variables.env
            sudo sed -i 's@STRICT_TRANSPORT_SECURITY=.*$@STRICT_TRANSPORT_SECURITY=max-age=86400@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CONTENT_SECURITY_POLICY=.*$@CONTENT_SECURITY_POLICY=object-src '"'"'none'"'"'; frame-ancestors '"'"'self'"'"';@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CONTENT_SECURITY_POLICY_REPORT_ONLY=.*$@CONTENT_SECURITY_POLICY_REPORT_ONLY=yes@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REFERRER_POLICY=.*$@REFERRER_POLICY=no-referrer@' /etc/bunkerweb/variables.env
            sudo sed -i 's@PERMISSIONS_POLICY=.*$@PERMISSIONS_POLICY=geolocation=(self), microphone=()@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DISABLE_FLOC=.*$@DISABLE_FLOC=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_FRAME_OPTIONS=.*$@X_FRAME_OPTIONS=DENY@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_CONTENT_TYPE_OPTIONS=.*$@X_CONTENT_TYPE_OPTIONS=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_XSS_PROTECTION=.*$@X_XSS_PROTECTION=0@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_DNS_PREFETCH_CONTROL=.*$@X_DNS_PREFETCH_CONTROL=on@' /etc/bunkerweb/variables.env
            export CUSTOM_HEADER="X-Test: test"
            export REMOVE_HEADERS="X-Powered-By X-AspNet-Version X-AspNetMvc-Version"
            export STRICT_TRANSPORT_SECURITY="max-age=86400"
            export CONTENT_SECURITY_POLICY="object-src 'none'; frame-ancestors 'self';"
            export CONTENT_SECURITY_POLICY_REPORT_ONLY="yes"
            export REFERRER_POLICY="no-referrer"
            export PERMISSIONS_POLICY="geolocation=(self), microphone=()"
            export DISABLE_FLOC="no"
            export X_FRAME_OPTIONS="DENY"
            export X_CONTENT_TYPE_OPTIONS=""
            export X_XSS_PROTECTION="0"
            export X_DNS_PREFETCH_CONTROL="on"
        fi
    elif [ "$test" = "no_httponly_flag" ] ; then
        echo "🎛️ Running tests without HttpOnly flag for cookies and with default values ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_FLAGS: ".*"$@COOKIE_FLAGS: "* SameSite=Lax"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CUSTOM_HEADER: "X-Test: test"@CUSTOM_HEADER: ""@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REMOVE_HEADERS: ".*"$@REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@KEEP_UPSTREAM_HEADERS: ".*"$@KEEP_UPSTREAM_HEADERS: "Content-Security-Policy Permission-Policy X-Frame-Options"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@STRICT_TRANSPORT_SECURITY: "max-age=86400"@STRICT_TRANSPORT_SECURITY: "max-age=31536000; includeSubDomains; preload"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "yes"@GENERATE_SELF_SIGNED_SSL: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY: ".*"$@CONTENT_SECURITY_POLICY: "object-src '"'"'none'"'"'; form-action '"'"'self'"'"'; frame-ancestors '"'"'self'"'"';"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"@CONTENT_SECURITY_POLICY_REPORT_ONLY: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@REFERRER_POLICY: "no-referrer"@REFERRER_POLICY: "strict-origin-when-cross-origin"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@PERMISSIONS_POLICY: ".*"$@PERMISSIONS_POLICY: "accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=()"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@DISABLE_FLOC: "yes"@DISABLE_FLOC: "no"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_FRAME_OPTIONS: "DENY"@X_FRAME_OPTIONS: "SAMEORIGIN"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_CONTENT_TYPE_OPTIONS: ""@X_CONTENT_TYPE_OPTIONS: "nosniff"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_XSS_PROTECTION: "0"@X_XSS_PROTECTION: "1; mode=block"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@X_DNS_PREFETCH_CONTROL: "off"@X_DNS_PREFETCH_CONTROL: "on"@' {} \;
        else
            sudo sed -i 's@COOKIE_FLAGS=.*$@COOKIE_FLAGS=* SameSite=Lax@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CUSTOM_HEADER=.*$@CUSTOM_HEADER=@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REMOVE_HEADERS=.*$@REMOVE_HEADERS=Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version@' /etc/bunkerweb/variables.env
            sudo sed -i 's@KEEP_UPSTREAM_HEADERS=.*$@KEEP_UPSTREAM_HEADERS=Content-Security-Policy Permission-Policy X-Frame-Options@' /etc/bunkerweb/variables.env
            sudo sed -i 's@STRICT_TRANSPORT_SECURITY=.*$@STRICT_TRANSPORT_SECURITY=max-age=31536000; includeSubDomains; preload@' /etc/bunkerweb/variables.env
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CONTENT_SECURITY_POLICY=.*$@CONTENT_SECURITY_POLICY=object-src '"'"'none'"'"'; form-action '"'"'self'"'"'; frame-ancestors '"'"'self'"'"';@' /etc/bunkerweb/variables.env
            sudo sed -i 's@CONTENT_SECURITY_POLICY_REPORT_ONLY=.*$@CONTENT_SECURITY_POLICY_REPORT_ONLY=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@REFERRER_POLICY=.*$@REFERRER_POLICY=strict-origin-when-cross-origin@' /etc/bunkerweb/variables.env
            sudo sed -i 's@PERMISSIONS_POLICY=.*$@PERMISSIONS_POLICY=accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=()@' /etc/bunkerweb/variables.env
            sudo sed -i 's@DISABLE_FLOC=.*$@DISABLE_FLOC=no@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_FRAME_OPTIONS=.*$@X_FRAME_OPTIONS=SAMEORIGIN@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_CONTENT_TYPE_OPTIONS=.*$@X_CONTENT_TYPE_OPTIONS=nosniff@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_XSS_PROTECTION=.*$@X_XSS_PROTECTION=1; mode=block@' /etc/bunkerweb/variables.env
            sudo sed -i 's@X_DNS_PREFETCH_CONTROL=.*$@X_DNS_PREFETCH_CONTROL=on@' /etc/bunkerweb/variables.env
            export COOKIE_FLAGS="* SameSite=Lax"
            export KEEP_UPSTREAM_HEADERS="Content-Security-Policy Permission-Policy X-Frame-Options"
            unset CUSTOM_HEADER
            unset REMOVE_HEADERS
            unset STRICT_TRANSPORT_SECURITY
            unset CONTENT_SECURITY_POLICY
            unset CONTENT_SECURITY_POLICY_REPORT_ONLY
            unset REFERRER_POLICY
            unset PERMISSIONS_POLICY
            unset DISABLE_FLOC
            unset X_FRAME_OPTIONS
            unset X_CONTENT_TYPE_OPTIONS
            unset X_XSS_PROTECTION
            unset X_DNS_PREFETCH_CONTROL
        fi
    elif [ "$test" = "multiple_no_httponly_flag" ] ; then
        echo "🎛️ Running tests with HttpOnly flag overridden for cookie \"bw_cookie\" and default cookies flags ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_FLAGS: ".*"$@COOKIE_FLAGS: "* HttpOnly SameSite=Lax"@' {} \;
            find . -type f -name 'docker-compose.*' -exec sed -i 's@KEEP_UPSTREAM_HEADERS: ".*"$@KEEP_UPSTREAM_HEADERS: "Content-Security-Policy X-Frame-Options"@' {} \;
            sed -i '27i \      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' docker-compose.yml
            sed -i '13i \      COOKIE_FLAGS_1: "bw_cookie SameSite=Lax"' docker-compose.test.yml
        else
            sudo sed -i 's@COOKIE_FLAGS=.*$@COOKIE_FLAGS=* HttpOnly SameSite=Lax@' /etc/bunkerweb/variables.env
            echo "COOKIE_FLAGS_1=bw_cookie SameSite=Lax" | sudo tee -a /etc/bunkerweb/variables.env
            sudo sed -i 's@KEEP_UPSTREAM_HEADERS=.*$@KEEP_UPSTREAM_HEADERS=Content-Security-Policy X-Frame-Options@' /etc/bunkerweb/variables.env
            export COOKIE_FLAGS="* HttpOnly SameSite=Lax"
            export COOKIE_FLAGS_1="bw_cookie SameSite=Lax"
            unset KEEP_UPSTREAM_HEADERS
        fi
    elif [ "$test" = "with_ssl" ] ; then
        echo "🎛️ Running tests with ssl ..."
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@GENERATE_SELF_SIGNED_SSL: "no"@GENERATE_SELF_SIGNED_SSL: "yes"@' {} \;
            sed -i '27d' docker-compose.yml
            sed -i '13d' docker-compose.test.yml
        else
            sudo sed -i 's@GENERATE_SELF_SIGNED_SSL=.*$@GENERATE_SELF_SIGNED_SSL=yes@' /etc/bunkerweb/variables.env
            sudo sed -i '$ d' /etc/bunkerweb/variables.env
            export GENERATE_SELF_SIGNED_SSL="yes"
        fi
    elif [ "$test" = "no_cookie_auto_secure_flag" ] ; then
        echo "🎛️ Running tests without cookie_auto_secure_flag ..."
        echo "ℹ️ Keeping the generated self-signed SSL certificate"
        if [ "$integration" == "docker" ] ; then
            find . -type f -name 'docker-compose.*' -exec sed -i 's@COOKIE_AUTO_SECURE_FLAG: "yes"@COOKIE_AUTO_SECURE_FLAG: "no"@' {} \;
        else
            sudo sed -i 's@COOKIE_AUTO_SECURE_FLAG=.*$@COOKIE_AUTO_SECURE_FLAG=no@' /etc/bunkerweb/variables.env
            export COOKIE_AUTO_SECURE_FLAG="no"
        fi
    fi

    echo "🎛️ Starting stack ..."
    if [ "$integration" == "docker" ] ; then
        docker compose up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🎛️ Up failed, retrying ... ⚠️"
            manual=1
            cleanup_stack
            manual=0
            docker compose up -d
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "🎛️ Up failed ❌"
                exit 1
            fi
        fi
    else
        sudo systemctl start bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "🎛️ Start failed ❌"
            exit 1
        fi
    fi

    # Check if stack is healthy
    echo "🎛️ Waiting for stack to be healthy ..."
    i=0
    if [ "$integration" == "docker" ] ; then
        while [ $i -lt 120 ] ; do
            containers=("headers-bw-1" "headers-bw-scheduler-1")
            healthy="true"
            for container in "${containers[@]}" ; do
                check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
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
    else
        healthy="false"
        retries=0
        while [[ $healthy = "false" && $retries -lt 5 ]] ; do
            while [ $i -lt 120 ] ; do
                if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                    echo "🎛️ Linux stack is healthy ✅"
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
                echo "🎛️ Linux stack is not healthy ❌"
                exit 1
            fi

            if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
                echo "🎛️ ⚠ Linux stack got an issue, restarting ..."
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
            echo "🎛️ Linux stack could not be healthy ❌"
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
        echo "🎛️ Test \"$test\" failed ❌"
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
        echo "🎛️ Test \"$test\" succeeded ✅"
    fi

    manual=1
    cleanup_stack
    manual=0

    echo " "
done

end=1
echo "🎛️ Tests are done ! ✅"
