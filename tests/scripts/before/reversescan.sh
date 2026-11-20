#!/bin/bash

integration="${1:-}"

# An address nginx's realip module can parse, NOT the container name. The spec puts this in
# X-Forwarded-For with REAL_IP_FROM=0.0.0.0/0, and realip silently ignores a value that is not an
# IP -- so `custom-api` left remote_addr at whatever Docker's plumbing produced: the gateway of
# the instance's primary bridge. The scan then hit the runner host instead of custom-api and the
# spec passed or failed on whether some unrelated container's published port happened to be
# reachable from that bridge. That is why it was green on Docker/Autoconf/Kubernetes and red on
# All-in-one, where it is not. 10.20.30.30 is custom-api's fixed address in
# tests/misc/docker/custom-api.yml, and it listens on 8000 -- one of REVERSE_SCAN_PORTS' defaults.
CUSTOM_API_IP="10.20.30.30"

if [ "$integration" == "Kubernetes" ]; then
    CUSTOM_API_IP=$(kubectl get svc -n misc svc-custom-api -o jsonpath='{.spec.clusterIP}')
fi

export CUSTOM_API_IP
