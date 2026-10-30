#!/bin/bash
set -euo pipefail

# Create the Authentik blueprint ConfigMap first so the Helm chart can mount it
# into the worker pod at creation time (the chart reads the ConfigMap list from
# blueprints.configMaps in authentik-chart-values.yml).
kubectl create configmap authentik-blueprint-bunkerweb \
    --from-file=bunkerweb.yaml=blueprints/bunkerweb.yaml \
    --dry-run=client -o yaml | kubectl apply -f -

# Install Authentik from the official Helm chart. Authentik 2026.2+ uses
# PostgreSQL for cache and channel layers, so Redis is disabled in the values
# file and no separate Redis subchart is pulled in.
helm repo add authentik https://charts.goauthentik.io >/dev/null 2>&1 || true
helm repo update authentik
helm upgrade --install -f authentik-chart-values.yml authentik authentik/authentik
