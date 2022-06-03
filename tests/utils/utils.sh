#!/bin/bash

function exec_docker_example() {
	if [ -d "/tmp/tests/$1" ] ; then
		sudo rm -rf "/tmp/tests/$1"
		if [ $? -ne 0 ] ; then
			return 1
		fi
	fi
	if [ ! -d "/tmp/tests" ] ; then
		mkdir /tmp/tests
		if [ $? -ne 0 ] ; then
			return 1
		fi
	fi
	cp -r "examples/$1" "/tmp/tests"
	if [ $? -ne 0 ] ; then
		return 1
	fi
	current_dir="$(pwd)"
	cd "/tmp/tests/$1"
	sed -i 's@bunkerity/bunkerweb:.*$@10.20.1.1:5000/bw-tests:latest@g' docker-compose.yml
	sed -i 's@\./bw\-data:/@/tmp/bw\-data:/@g' docker-compose.yml
	sed -i 's@- bw_data:/@- /tmp/bw\-data:/@g' docker-compose.yml
	sed -i "s@www.example.com@${TEST_DOMAIN1}@g" docker-compose.yml
	sed -i "s@app1.example.com@${TEST_DOMAIN1_1}@g" docker-compose.yml
	sed -i "s@app2.example.com@${TEST_DOMAIN1_2}@g" docker-compose.yml
	sed -i "s@app3.example.com@${TEST_DOMAIN1_3}@g" docker-compose.yml
	find "/tmp/tests/$1" -name "www.example.com" -exec /usr/bin/rename "s/www.example.com/${TEST_DOMAIN1}/" {} \+
	find "/tmp/tests/$1" -name "app1.example.com" -exec /usr/bin/rename "s/app1.example.com/${TEST_DOMAIN1_1}/" {} \+
	find "/tmp/tests/$1" -name "app2.example.com" -exec /usr/bin/rename "s/app2.example.com/${TEST_DOMAIN1_2}/" {} \+
	find "/tmp/tests/$1" -name "app3.example.com" -exec /usr/bin/rename "s/app3.example.com/${TEST_DOMAIN1_3}/" {} \+
	if [ -f setup.sh ] ; then
		sudo ./setup.sh
	fi
	for folder in $(echo "configs plugins www") ; do
		sudo bash -c "find /tmp/bw-data/$folder -type f -exec rm -f {} \;"
	done
	if [ -d ./bw-data ] ; then
		sudo bash -c "cp -a ./bw-data/* /tmp/bw-data"
	fi
	docker-compose pull > /dev/null 2>&1
	ret=$(docker-compose up -d 2>&1)
	if [ "$?" -ne 0 ] ; then
		sudo docker-compose down -v > /dev/null 2>&1
		cd "$current_dir"
		sudo rm -rf "/tmp/tests/$1"
		echo "$ret"
		return 1
	fi
	cd "$current_dir"
}

function exec_swarm_example() {
	if [ -d "/tmp/tests/$1" ] ; then
		sudo rm -rf "/tmp/tests/$1"
		if [ $? -ne 0 ] ; then
			return 1
		fi
	fi
	if [ ! -d "/tmp/tests" ] ; then
		mkdir /tmp/tests
		if [ $? -ne 0 ] ; then
			return 1
		fi
	fi
	cp -r "examples/$1" "/tmp/tests"
	if [ $? -ne 0 ] ; then
		return 1
	fi
	current_dir="$(pwd)"
	cd "/tmp/tests/$1"
	sed -i "s@www.example.com@${TEST_DOMAIN1}@g" stack.yml
	sed -i "s@app1.example.com@${TEST_DOMAIN1}@g" stack.yml
	sed -i "s@app2.example.com@${TEST_DOMAIN2}@g" stack.yml
	sed -i "s@app3.example.com@${TEST_DOMAIN3}@g" stack.yml
	sed -i "s@www.example.com@${TEST_DOMAIN1}@g" setup.sh
	sed -i "s@app1.example.com@${TEST_DOMAIN1}@g" setup.sh
	sed -i "s@app2.example.com@${TEST_DOMAIN2}@g" setup.sh
	sed -i "s@app3.example.com@${TEST_DOMAIN3}@g" setup.sh
	find "/tmp/tests/$1" -name "www.example.com" -exec /usr/bin/rename "s/www.example.com/${TEST_DOMAIN1}/" {} \+
	find "/tmp/tests/$1" -name "app1.example.com" -exec /usr/bin/rename "s/app1.example.com/${TEST_DOMAIN1}/" {} \+
	find "/tmp/tests/$1" -name "app2.example.com" -exec /usr/bin/rename "s/app2.example.com/${TEST_DOMAIN2}/" {} \+
	find "/tmp/tests/$1" -name "app3.example.com" -exec /usr/bin/rename "s/app3.example.com/${TEST_DOMAIN3}/" {} \+
	if [ -f setup.sh ] ; then
		sudo ./setup.sh
	fi
	docker stack rm "$1" > /dev/null 2>&1
	docker stack deploy -c stack.yml "$1"
	if [ "$?" -ne 0 ] ; then
		cd "$current_dir"
		sudo rm -rf "/tmp/tests/$1"
		return 1
	fi
	cd "$current_dir"
}

function exec_k8s_example() {
	if [ -d "/tmp/tests/$1" ] ; then
		sudo rm -rf "/tmp/tests/$1"
		if [ $? -ne 0 ] ; then
			return 1
		fi
	fi
	if [ ! -d "/tmp/tests" ] ; then
		mkdir /tmp/tests
		if [ $? -ne 0 ] ; then
			return 1
		fi
	fi
	cp -r "examples/$1" "/tmp/tests"
	if [ $? -ne 0 ] ; then
		return 1
	fi
	current_dir="$(pwd)"
	cd "/tmp/tests/$1"
	sed -i "s@www.example.com@${TEST_DOMAIN1}@g" *.yml
	sed -i "s@app1.example.com@${TEST_DOMAIN1}@g" *.yml
	sed -i "s@app2.example.com@${TEST_DOMAIN2}@g" *.yml
	sed -i "s@app3.example.com@${TEST_DOMAIN3}@g" *.yml
	find "/tmp/tests/$1" -name "www.example.com" -exec /usr/bin/rename "s/www.example.com/${TEST_DOMAIN1}/" {} \+
	find "/tmp/tests/$1" -name "app1.example.com" -exec /usr/bin/rename "s/app1.example.com/${TEST_DOMAIN1}/" {} \+
	find "/tmp/tests/$1" -name "app2.example.com" -exec /usr/bin/rename "s/app2.example.com/${TEST_DOMAIN2}/" {} \+
	find "/tmp/tests/$1" -name "app3.example.com" -exec /usr/bin/rename "s/app3.example.com/${TEST_DOMAIN3}/" {} \+
	if [ -f setup.sh ] ; then
		sudo ./setup.sh
	fi
	for yml in $(ls *.yml) ; do
		if [ "$yml" != "ingress.yml" ] ; then
			sudo kubectl delete -f "$yml" > /dev/null 2> /dev/null
			sudo kubectl apply -f "$yml"
			if [ $? -ne 0 ] ; then
				cd "$current_dir"
				sudo kubectl delete -f "/tmp/tests/$1" > /dev/null 2>&1
				rm -rf "/tmp/tests/$1"
				return 1
			fi
		fi
	done
	sudo kubectl delete -f "ingress.yml" > /dev/null 2> /dev/null
	sudo kubectl apply -f "ingress.yml"
	if [ "$?" -ne 0 ] ; then
		cd "$current_dir"
		sudo kubectl delete -f "/tmp/tests/$1" > /dev/null 2>&1
		rm -rf "/tmp/tests/$1"
		return 1
	fi
	cd "$current_dir"
}

function curl_assert() {
	url="$1"
	str="$2"
	max_wait=$3
	ws="$4"
	if [ "$ws" != "" ] ; then
		cp ./tests/utils/websocat_amd64-linux /tmp/
		chmod +x /tmp/websocat_amd64-linux
	fi
	current_wait=0
	while [ $current_wait -le $max_wait ] ; do
		if [ "$ws" = "" ] ; then
			data="$(curl -k -L -s --cookie /dev/null -H "User-Agent: LegitOne" "$url" | grep -i "$str")"
		else
			data="$(echo "test" | /tmp/websocat_amd64-linux - --text wss://test1.bunkerity.com/ws/ | grep -i "$str")"
		fi
		if [ "$data" != "" ] && [ $? -eq 0 ] ; then
			return 0
		fi
		current_wait=$((current_wait+1))
		sleep 1
	done
	return 1
}

function rm_example() {
	if [ ! -d "/tmp/tests/$1" ] ; then
		return 1
	fi
	current_dir="$(pwd)"
	cd "/tmp/tests/$1"
	sudo docker-compose down -v > /dev/null 2>&1
	cd "$current_dir"
	sudo rm -rf "/tmp/tests/$1"
}

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
	#echo $output
	return 0
}
