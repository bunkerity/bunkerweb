#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f moodle-chart-values.yml moodle bitnami/moodle
