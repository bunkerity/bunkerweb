#!/bin/bash

helm repo add nextcloud https://nextcloud.github.io/helm/
helm install -f nextcloud-chart-values.yml nextcloud nextcloud/nextcloud
