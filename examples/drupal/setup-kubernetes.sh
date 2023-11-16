#!/bin/bash

helm repo add bitnami https://charts.bitnami.com/bitnami
helm install -f drupal-chart-values.yml drupal bitnami/drupal
