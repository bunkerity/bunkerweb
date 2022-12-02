#!/bin/bash

helm repo add wordpress https://charts.bitnami.com/bitnami
helm install -f wordpress-chart-values.yml wordpress bitnami/wordpress
