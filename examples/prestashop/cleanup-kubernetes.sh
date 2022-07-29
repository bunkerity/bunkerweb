#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm delete prestashop
kubectl delete pvc data-prestashop-mariadb-0