#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm repo add wordpress https://charts.bitnami.com/bitnami
helm install -f wordpress-chart-values.yml wordpress bitnami/wordpress