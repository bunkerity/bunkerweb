#!/bin/bash

helm install -f moodle-chart-values.yml moodle oci://registry-1.docker.io/bitnamicharts/moodle
