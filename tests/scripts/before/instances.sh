#!/bin/bash

integration="${1:-}"

if [ "$integration" == "Linux" ] && [ -f /etc/bunkerweb/variables.env ]; then
  if [ "$(uname -s)" == "FreeBSD" ] ; then
    chmod 777 /etc/bunkerweb/variables.env
  else
    docker exec -u 0 bunkerweb-linux chmod 777 /etc/bunkerweb/variables.env
  fi
fi

if [ "$integration" == "Kubernetes" ]; then
  kubectl apply -f tests/scripts/before/instances.yml
else
  docker compose -f tests/scripts/before/docker-instances.yml up -d
fi
