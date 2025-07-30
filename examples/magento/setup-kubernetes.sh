#!/bin/bash

helm install -f magento-chart-values.yml magento oci://registry-1.docker.io/bitnamicharts/magento
