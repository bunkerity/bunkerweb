#!/bin/bash

# Resolve celery and the import path explicitly: the worker image puts both on PATH and
# PYTHONPATH, but the all-in-one image does neither (supervisord injects them per service),
# so assuming them would report a perfectly healthy worker as dead there.
CELERY_BIN="$(command -v celery || echo /usr/share/bunkerweb/deps/python/bin/celery)"
# The same list supervisord gives the worker service in the all-in-one image
# (/etc/supervisor.d/worker.ini). `worker/app.py` imports `job_queues`, which lives in
# `utils/`, so a shorter path here fails to import the Celery app at all: the probe reported
# a dead worker on every run, the container never turned healthy, and every All-in-one spec
# timed out waiting for it -- while the worker itself was running and executing jobs.
export PYTHONPATH="/usr/share/bunkerweb:/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/db:/usr/share/bunkerweb/utils:/usr/share/bunkerweb/api:${PYTHONPATH:-}"

"$CELERY_BIN" -A worker.app inspect ping \
  --destination "worker@${HOSTNAME:-$(hostname)}" \
  --timeout 10 2>/dev/null | grep -q "pong"
