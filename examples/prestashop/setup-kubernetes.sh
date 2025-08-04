#!/bin/bash

helm install -f prestashop-chart-values.yml prestashop oci://registry-1.docker.io/bitnamicharts/prestashop
