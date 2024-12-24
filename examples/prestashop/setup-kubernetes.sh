#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f prestashop-chart-values.yml prestashop bitnami/prestashop
