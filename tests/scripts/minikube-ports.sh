#!/usr/bin/env bash

# host:container mappings shared by local build.sh and the Kubernetes CI workflow.
minikube_ports=(
  "80:80" "443:443" "5000:5000" "5001:5001" "5443:5443"
  "${UI_HOST_PORT:-7000}:30070" "8000:30080" "8888:30088"
  "3306:30306" "5432:30432"
  "6380:30379" "6381:30380" "6382:30381" "6479:30479" "6480:30482"
  "26379:32379" "26380:32380" "26381:32381"
  "26479:32479" "26480:32480" "26481:32481"
)

minikube_port_args=()
for mapping in "${minikube_ports[@]}" ; do
  minikube_port_args+=(--ports "127.0.0.1:${mapping}")
done

if [[ "${BASH_SOURCE[0]}" == "$0" ]] ; then
  printf '%s\n' "${minikube_port_args[*]}"
fi
