#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm delete magento
kubectl delete pvc data-magento-elasticsearch-data-0
kubectl delete pvc data-magento-elasticsearch-master-0
kubectl delete pvc data-magento-mariadb-0