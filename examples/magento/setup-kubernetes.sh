#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f magento-chart-values.yml magento bitnami/magento
