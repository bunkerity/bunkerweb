#!/bin/bash

. ./tests/utils/utils.sh

. /opt/.runner_env

function single_docker_test() {
	example="$1"
	wait_time="$2"
	shift
	shift
	asserts=("$@")
	echo "Testing $example ..."
	exec_docker_example "$example"
	if [ $? -ne 0 ] ; then
		echo "$example failed (exec) ..."
		exit 1
	fi
	for assert in "${asserts[@]}" ; do
		url="$(echo "$assert" | cut -d ' ' -f 1)"
		str="$(echo "$assert" | cut -d ' ' -f 2)"
		if [ "$(echo "$example" | grep websocket)" = "" ] ; then
			curl_assert "$url" "$str" "$wait_time"
		else
			curl_assert "$url" "$str" "$wait_time" "ws"
		fi
		ret=$?
		if [ $ret -ne 0 ] ; then
			current_dir="$(pwd)"
			cd "/tmp/tests/$example"
			docker-compose logs
			cd "$current_dir"
			rm_example "$example"
			echo "$example failed (assert) ..."
			exit 1
		fi
	done
	rm_example "$example"
	echo "$example success !"
}

# Setup data folder if not present
if [ ! -d "/tmp/bw-data" ] ; then
	mkdir /tmp/bw-data
	sudo chown 101:101 /tmp/bw-data
	sudo chmod 777 /tmp/bw-data
fi

echo "Running Docker tests ..."

# authelia
single_docker_test "authelia" "60" "https://$TEST_DOMAIN1_1 authelia" "https://$TEST_DOMAIN1_2 authelia"

# authentik
# TODO : find a way to load a basic configuration for automatic tests
# single_docker_test "authentik" "60" "https://$TEST_DOMAIN1_1 authentik" "https://$TEST_DOMAIN1_2 authentik"

# drupal
single_docker_test "drupal" "60" "https://$TEST_DOMAIN1 drupal"

# ghost
single_docker_test "ghost" "30" "https://$TEST_DOMAIN1 ghost"

# gogs
single_docker_test "gogs" "30" "https://$TEST_DOMAIN1 gogs"

# hardened
single_docker_test "hardened" "30" "https://$TEST_DOMAIN1 hello"

# joomla
single_docker_test "joomla" "60" "https://$TEST_DOMAIN1 joomla"

# load-balancer
single_docker_test "load-balancer" "30" "https://$TEST_DOMAIN1 hello"

# magento
single_docker_test "magento" "180" "https://$TEST_DOMAIN1 magento"

# moodle
single_docker_test "moodle" "300" "https://$TEST_DOMAIN1 moodle"

# nextcloud
single_docker_test "nextcloud" "120" "https://$TEST_DOMAIN1 nextcloud"

# passbolt
single_docker_test "passbolt" "120" "https://$TEST_DOMAIN1 passbolt"

# php-multisite
single_docker_test "php-multisite" "30" "https://$TEST_DOMAIN1_1 app1" "https://$TEST_DOMAIN1_2 app2"

# php-singlesite
single_docker_test "php-singlesite" "30" "https://$TEST_DOMAIN1 hello"

# prestashop
single_docker_test "prestashop" "120" "https://$TEST_DOMAIN1 prestashop"

# redmine
single_docker_test "redmine" "60" "https://$TEST_DOMAIN1 redmine"

# reverse-proxy-multisite
single_docker_test "reverse-proxy-multisite" "30" "https://$TEST_DOMAIN1_1 app1" "https://$TEST_DOMAIN1_2 hello"

# reverse-proxy-singlesite
single_docker_test "reverse-proxy-singlesite" "30" "https://$TEST_DOMAIN1/app1/ app1" "https://$TEST_DOMAIN1/app2/ hello"

# reverse-proxy-websocket
cp ./tests/utils/websocat_amd64-linux /tmp/
chmod +x ./tests/utils/websocat_amd64-linux
# todo

# tomcat
single_docker_test "tomcat" "30" "https://$TEST_DOMAIN1 tomcat"

# wordpress
single_docker_test "wordpress" "30" "https://$TEST_DOMAIN1 wordpress"

exit 0
