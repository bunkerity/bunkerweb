#!/bin/bash

helm install -f redmine-chart-values.yml redmine oci://registry-1.docker.io/bitnamicharts/redmine
