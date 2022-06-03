#!/bin/bash

. ./tests/utils/utils.sh

. /opt/.runner_env

function single_k8s_test() {
	example="$1"
	wait_time="$2"
	shift
	shift
	asserts=("$@")
	echo "Testing $example ..."
	exec_k8s_example "$example"
	if [ $? -ne 0 ] ; then
		for pod in $(sudo kubectl get pods | cut -d ' ' -f 1 | grep -v NAME) ; do
			sudo kubectl logs $pod
		done
		cd "/tmp/k8s"
		sudo kubectl delete -f bunkerweb.yml > /dev/null 2>&1
		sudo kubectl delete -f rbac.yml > /dev/null 2>&1
		sudo kubectl delete -f k8s.yml > /dev/null 2>&1
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
			for pod in $(sudo kubectl get pods | cut -d ' ' -f 1 | grep -v NAME) ; do
				sudo kubectl logs $pod
			done
			cd "/tmp/k8s"
			sudo kubectl delete -f bunkerweb.yml > /dev/null 2>&1
			sudo kubectl delete -f rbac.yml > /dev/null 2>&1
			sudo kubectl delete -f k8s.yml > /dev/null 2>&1
			cd "/tmp/tests/$example"
			for yml in $(ls *.yml) ; do
				sudo kubectl delete -f "$yml"
			done
			echo "$example failed (curl) ..."
			exit 1
		fi
	done
	current_dir="$(pwd)"
	cd "/tmp/tests/$example"
	for yml in $(ls *.yml) ; do
		sudo kubectl delete -f "$yml"
	done
	cd "$current_dir"
	echo "$example success !"
}

echo "Running k8s tests ..."

# Start k8s
if [ ! -d "/tmp/k8s" ] ; then
	mkdir /tmp/k8s
fi
rm -rf /tmp/k8s/*
cp -r ./integrations/kubernetes/* /tmp/k8s
cp ./tests/utils/k8s.yml /tmp/k8s
sed -i 's@bunkerity/bunkerweb:.*$@10.20.1.1:5000/bw-tests:latest@g' /tmp/k8s/bunkerweb.yml
sed -i 's@bunkerity/bunkerweb-autoconf:.*$@10.20.1.1:5000/bw-autoconf-tests:latest@g' /tmp/k8s/bunkerweb.yml
sed -i 's@ifNotPresent@Always@g' /tmp/k8s/bunkerweb.yml
current_dir="$(pwd)"
cd "/tmp/k8s"

# delete old objects
sudo kubectl delete -f bunkerweb.yml > /dev/null 2>&1
sudo kubectl delete -f rbac.yml > /dev/null 2>&1
sudo kubectl delete -f k8s.yml > /dev/null 2>&1
current_wait=0
while [ 1 ] ; do
	if [ $current_wait -gt 30 ] ; then
		echo "can't remove old k8s objects"
		exit 1
	fi
	if [ "$(sudo kubectl get pods | grep "bunkerweb")" = "" ] ; then
		break
	fi
	current_wait=$((current_wait+1))
	sleep 1
done

# start the controller and instances
sudo kubectl apply -f k8s.yml
if [ $? -ne 0 ] ; then
	echo "k8s failed (deploy k8s.yml)"
	exit 1
fi
sudo kubectl apply -f rbac.yml
if [ $? -ne 0 ] ; then
	sudo kubectl delete -f k8s.yml
	echo "k8s failed (deploy rbac.yml)"
	exit 1
fi
sudo kubectl apply -f bunkerweb.yml
if [ $? -ne 0 ] ; then
	sudo kubectl delete -f rbac.yml
	sudo kubectl delete -f k8s.yml
	echo "k8s failed (deploy bunkerweb.yml)"
	exit 1
fi
current_wait=0
healthy="no"
while [ $current_wait -lt 30 ] ; do
	check="$(sudo kubectl get pods | grep bunkerweb | grep -v Running)"
	if [ "$check" = "" ] ; then
		healthy="yes"
		break
	fi
	current_wait=$((current_wait+1))
	sleep 1
done
if [ "$healthy" = "no" ] ; then
	sudo kubectl get pods
	sudo kubectl delete -f bunkerweb.yml > /dev/null 2>&1
	sudo kubectl delete -f rbac.yml > /dev/null 2>&1
	sudo kubectl delete -f k8s.yml > /dev/null 2>&1
	echo "k8s failed (not healthy)"
	exit 1
fi
cd "$current_dir"
sleep 60

# reverse
single_k8s_test "kubernetes-ingress" "120" "https://$TEST_DOMAIN1 hello" "https://$TEST_DOMAIN2 hello" "https://$TEST_DOMAIN3 hello"

# configs
single_k8s_test "kubernetes-configs" "120" "https://$TEST_DOMAIN1/app1 app1" "https://$TEST_DOMAIN2/app2 app2" "https://$TEST_DOMAIN3/app3 app3" "https://$TEST_DOMAIN1/hello hello" "https://$TEST_DOMAIN2/hello hello" "https://$TEST_DOMAIN3/hello hello"

# cleanup
current_dir="$(pwd)"
cd "/tmp/k8s"
sudo kubectl delete -f bunkerweb.yml > /dev/null 2>&1
sudo kubectl delete -f rbac.yml > /dev/null 2>&1
sudo kubectl delete -f k8s.yml > /dev/null 2>&1
cd "$current_dir"

exit 0
