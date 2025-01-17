#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f ghost-chart-values.yml ghost bitnami/ghost
