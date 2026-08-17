#!/bin/bash

integration="${1:-}"

if [ "$integration" == "Kubernetes" ]; then
  kubectl delete -f tests/scripts/before/instances.yml
else
  docker compose -f tests/scripts/before/docker-instances.yml down -v
fi
