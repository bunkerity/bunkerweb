#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm delete redmine
kubectl delete pvc data-redmine-mariadb-0
kubectl delete pvc data-redmine-postgresql-0