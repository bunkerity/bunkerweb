#!/bin/bash

helm install -f wordpress-chart-values.yml wordpress oci://registry-1.docker.io/bitnamicharts/wordpress
