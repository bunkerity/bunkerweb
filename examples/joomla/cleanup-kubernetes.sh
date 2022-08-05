#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm delete joomla
kubectl delete pvc data-joomla-mariadb-0