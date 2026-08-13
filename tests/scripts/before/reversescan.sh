#!/bin/bash

integration="${1:-}"

CUSTOM_API_IP="custom-api"

if [ "$integration" == "Kubernetes" ]; then
    CUSTOM_API_IP=$(kubectl get svc -n misc svc-custom-api -o jsonpath='{.spec.clusterIP}')
fi

export CUSTOM_API_IP
