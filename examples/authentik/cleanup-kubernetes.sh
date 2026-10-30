#!/bin/bash
set -euo pipefail

helm uninstall authentik 2>/dev/null || true
kubectl delete configmap authentik-blueprint-bunkerweb --ignore-not-found=true
