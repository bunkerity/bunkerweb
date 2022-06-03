#!/bin/bash

. ./tests/utils/utils.sh

. /opt/.runner_env

function single_swarm_test() {
	example="$1"
	wait_time="$2"
	shift
	shift
	asserts=("$@")
	echo "Testing $example ..."
	exec_swarm_example "$example"
	if [ $? -ne 0 ] ; then
		docker service logs bunkerweb_mybunker
		docker service logs bunkerweb_myautoconf
		docker stack rm bunkerweb > /dev/null 2>&1
		for config in $(docker config ls --format "{{ .ID }}") ; do
			docker config rm $config
		done
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
			docker service logs bunkerweb_mybunker
			docker service logs bunkerweb_myautoconf
			for service in $(docker stack services --format "{{ .Name }}" "$example") ; do
				docker service logs "$service"
			done
			docker config ls
			docker stack rm bunkerweb > /dev/null 2>&1
			docker stack rm "$example" > /dev/null 2>&1
			docker network rm services_net autoconf_net > /dev/null 2>&1
			for config in $(docker config ls --format "{{ .ID }}") ; do
				docker config rm $config
			done
			echo "$example failed (curl) ..."
			exit 1
		fi
	done
	docker stack rm "$example"
	for config in $(docker config ls --format "{{ .ID }}") ; do
		docker config rm $config
	done
	echo "$example success !"
}

echo "Running swarm tests ..."

# Start swarm
if [ ! -d "/tmp/swarm" ] ; then
	mkdir /tmp/swarm
fi
rm -rf /tmp/swarm/*
cp -r ./integrations/swarm/* /tmp/swarm
sed -i 's@bunkerity/bunkerweb:.*$@10.20.1.1:5000/bw-tests:latest@g' /tmp/swarm/stack.yml
sed -i 's@bunkerity/bunkerweb-autoconf:.*$@10.20.1.1:5000/bw-autoconf-tests:latest@g' /tmp/swarm/stack.yml
current_dir="$(pwd)"
cd "/tmp/swarm"
echo "starting swarm stack ..."
docker stack rm bunkerweb > /dev/null 2>&1
current_wait=0
while [ 1 ] ; do
	if [ $current_wait -gt 30 ] ; then
		echo "can't remove old swarm stack"
		exit 1
	fi
	if [ "$(docker stack ls | grep bunkerweb)" = "" ] ; then
		break
	fi
	current_wait=$((current_wait+1))
	sleep 1
done
docker network rm services_net autoconf_net > /dev/null 2>&1
ret="$(docker stack deploy -c stack.yml bunkerweb 2>&1)"
if [ $? -ne 0 ] ; then
	echo "$ret"
	echo "swarm failed (deploy)"
	exit 1
fi
current_wait=0
healthy="no"
while [ $current_wait -lt 30 ] ; do
	check="$(docker stack ps --no-trunc --format "{{ .CurrentState }}" bunkerweb | grep -v "Running" 2>&1)"
	if [ "$check" = "" ] ; then
		healthy="yes"
		break
	fi
	current_wait=$((current_wait+1))
	sleep 1
done
if [ "$healthy" = "no" ] ; then
	echo "$ret"
	docker service logs bunkerweb_mybunker
	docker service logs bunkerweb_myautoconf
	docker stack rm bunkerweb > /dev/null 2>&1
	echo "swarm failed (not healthy)"
	exit 1
fi
cd "$current_dir"
sleep 60

# reverse
single_swarm_test "swarm-reverse-proxy" "120" "https://$TEST_DOMAIN1 hello" "https://$TEST_DOMAIN2 hello" "https://$TEST_DOMAIN3 hello"

# configs
single_swarm_test "swarm-configs" "120" "https://$TEST_DOMAIN1/app1 app1" "https://$TEST_DOMAIN2/app2 app2" "https://$TEST_DOMAIN3/app3 app3" "https://$TEST_DOMAIN1/hello hello" "https://$TEST_DOMAIN2/hello hello" "https://$TEST_DOMAIN3/hello hello"

# cleanup
current_dir="$(pwd)"
cd "/tmp/swarm"
docker stack rm bunkerweb > /dev/null 2>&1
cd "$current_dir"

exit 0
