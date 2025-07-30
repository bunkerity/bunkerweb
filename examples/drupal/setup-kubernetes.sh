#!/bin/bash

helm install -f drupal-chart-values.yml drupal oci://registry-1.docker.io/bitnamicharts/drupal
