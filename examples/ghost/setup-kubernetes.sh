#!/bin/bash

helm install -f ghost-chart-values.yml ghost oci://registry-1.docker.io/bitnamicharts/ghost
