#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f redmine-chart-values.yml redmine bitnami/redmine
