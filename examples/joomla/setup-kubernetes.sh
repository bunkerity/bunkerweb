#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f joomla-chart-values.yml joomla bitnami/joomla
