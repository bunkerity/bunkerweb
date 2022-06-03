#!/bin/bash

. ./tests/utils/utils.sh

. /opt/.runner_env

function single_autoconf_test() {
	example="$1"
	wait_time="$2"
	shift
	shift
	asserts=("$@")
	echo "Testing $example ..."
	exec_docker_example "$example"
	if [ $? -ne 0 ] ; then
		cd /tmp/autoconf
		docker-compose logs
		docker-compose down -v > /dev/null 2>&1
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
			cd /tmp/autoconf
			docker-compose logs
			docker-compose down -v > /dev/null 2>&1
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
	sudo chown root:101 /tmp/bw-data
	sudo chmod 770 /tmp/bw-data
fi
for folder in $(echo "configs plugins www") ; do
	sudo rm -rf "/tmp/bw-data/${folder}" > /dev/null 2>&1
done

echo "Running autoconf tests ..."

# Start autoconf
if [ ! -d "/tmp/autoconf" ] ; then
	mkdir /tmp/autoconf
fi
rm -rf /tmp/autoconf/*
cp -r ./integrations/autoconf/* /tmp/autoconf
sed -i 's@bunkerity/bunkerweb:.*$@10.20.1.1:5000/bw-tests:latest@g' /tmp/autoconf/docker-compose.yml
sed -i 's@bunkerity/bunkerweb-autoconf:.*$@10.20.1.1:5000/bw-autoconf-tests:latest@g' /tmp/autoconf/docker-compose.yml
sed -i 's@\./bw\-data:/@/tmp/bw\-data:/@g' /tmp/autoconf/docker-compose.yml
current_dir="$(pwd)"
cd "/tmp/autoconf"
echo "starting autoconf ..."
docker-compose down -v > /dev/null 2>&1
docker-compose pull > /dev/null 2>&1
ret="$(docker-compose up -d 2>&1)"
if [ $? -ne 0 ] ; then
	echo "$ret"
	echo "autoconf failed (up)"
fi
current_wait=0
healthy="no"
while [ $current_wait -lt 30 ] ; do
	check="$(docker inspect --format "{{json .State.Health }}" autoconf_mybunker_1 | grep healthy)"
	if [ "$check" != "" ] ; then
		healthy="yes"
		break
	fi
	current_wait=$((current_wait+1))
	sleep 1
done
if [ "$healthy" = "no" ] ; then
	echo "$ret"
	docker-compose logs
	docker-compose down -v > /dev/null 2>&1
	echo "autoconf failed (not healthy)"
	exit 1
fi
cd "$current_dir"

# reverse
single_autoconf_test "autoconf-reverse-proxy" "60" "https://$TEST_DOMAIN1_1 hello" "https://$TEST_DOMAIN1_2 hello" "https://$TEST_DOMAIN1_3 hello"

# php
single_autoconf_test "autoconf-php" "60" "https://$TEST_DOMAIN1_1 app1" "https://$TEST_DOMAIN1_2 app2" "https://$TEST_DOMAIN1_3 app3"

# cleanup
current_dir="$(pwd)"
cd "/tmp/autoconf"
docker-compose down -v > /dev/null 2>&1
cd "$current_dir"

exit 0
