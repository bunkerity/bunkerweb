#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f prestashop-chart-values.yml prestashop bitnami/prestashop