#!/bin/bash

# Resolve celery and the import path explicitly: the worker image puts both on PATH and
# PYTHONPATH, but the all-in-one image does neither (supervisord injects them per service),
# so assuming them would report a perfectly healthy worker as dead there.
CELERY_BIN="$(command -v celery || echo /usr/share/bunkerweb/deps/python/bin/celery)"
export PYTHONPATH="/usr/share/bunkerweb:/usr/share/bunkerweb/deps/python:${PYTHONPATH:-}"

"$CELERY_BIN" -A worker.app inspect ping \
  --destination "worker@${HOSTNAME:-$(hostname)}" \
  --timeout 10 2>/dev/null | grep -q "pong"
