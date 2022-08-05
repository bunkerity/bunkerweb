#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm delete moodle
kubectl delete pvc data-moodle-mariadb-0