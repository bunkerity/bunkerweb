#!/bin/bash

# Check if supervisord is running with proper configuration
pgrep supervisord >/dev/null || { echo "Supervisord not running"; exit 1; }

# Check BunkerWeb service status (always required)
status=$(supervisorctl status "bunkerweb" 2>/dev/null)
if ! echo "$status" | grep -q "RUNNING"; then
  echo "Service bunkerweb is not running: $status"
  exit 1
fi

# Check BunkerWeb PID file exists
if [ ! -f /var/run/bunkerweb/nginx.pid ]; then
  echo "BunkerWeb PID file not found"
  exit 1
fi

/usr/share/bunkerweb/helpers/healthcheck.sh
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
  echo "BunkerWeb health check failed"
  exit 1
fi

# Check UI service status only if enabled
if [ "${SERVICE_UI:-yes}" = "yes" ]; then
  status=$(supervisorctl status "ui" 2>/dev/null)
  if ! echo "$status" | grep -q "RUNNING"; then
    echo "Service ui is not running: $status"
    exit 1
  fi

  /usr/share/bunkerweb/helpers/healthcheck-ui.sh
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "UI health check failed"
    exit 1
  fi
else
  echo "UI service check skipped (disabled by SERVICE_UI setting)"
fi

# Check scheduler service status only if enabled
if [ "${SERVICE_SCHEDULER:-yes}" = "yes" ]; then
  status=$(supervisorctl status "scheduler" 2>/dev/null)
  if ! echo "$status" | grep -q "RUNNING"; then
    echo "Service scheduler is not running: $status"
    exit 1
  fi

  /usr/share/bunkerweb/helpers/healthcheck-scheduler.sh
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "Scheduler health check failed"
    exit 1
  fi
else
  echo "Scheduler service check skipped (disabled by SERVICE_SCHEDULER setting)"
fi

# Check autoconf service status only if enabled
if [ "${AUTOCONF_MODE:-no}" = "yes" ]; then
  status=$(supervisorctl status "autoconf" 2>/dev/null)
  if ! echo "$status" | grep -q "RUNNING"; then
    echo "Service autoconf is not running: $status"
    exit 1
  fi

  /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "Autoconf health check failed"
    exit 1
  fi
else
  echo "Autoconf service check skipped (disabled by AUTOCONF_MODE setting)"
fi

# Check API service status only if enabled
if [ "${SERVICE_API:-yes}" = "yes" ]; then
  status=$(supervisorctl status "api" 2>/dev/null)
  if ! echo "$status" | grep -q "RUNNING"; then
    echo "Service api is not running: $status"
    exit 1
  fi

  /usr/share/bunkerweb/helpers/healthcheck-api.sh
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
    echo "API health check failed"
    exit 1
  fi
else
  echo "API service check skipped (disabled by SERVICE_API setting)"
fi

# Check embedded Redis only when the AIO is supposed to run it.
# Mirror the entrypoint gate (entrypoint.sh): USE_REDIS=yes and REDIS_HOST is
# unset/local. A dead embedded Redis must flip the container to unhealthy instead
# of silently degrading every request to the local fallback.
if [ "${USE_REDIS:-no}" = "yes" ] && { [ "${REDIS_HOST:-127.0.0.1}" = "127.0.0.1" ] || [ "${REDIS_HOST:-127.0.0.1}" = "localhost" ]; }; then
  status=$(supervisorctl status "redis" 2>/dev/null)
  if ! echo "$status" | grep -q "RUNNING"; then
    echo "Embedded Redis is enabled (USE_REDIS=yes) but not running: $status"
    exit 1
  fi
  # Liveness probe: catches a process that is RUNNING but not serving (e.g. still
  # LOADING a large AOF/RDB on boot, or wedged). PING is rejected during loading,
  # so a non-PONG reply means Redis is up but unusable. (OOM/MISCONF still answer
  # PONG; those write-rejection states are handled at the application layer.)
  if command -v redis-cli >/dev/null 2>&1; then
    [ -n "${REDIS_PASSWORD:-}" ] && export REDISCLI_AUTH="${REDIS_PASSWORD}"
    if [ "$(redis-cli -h 127.0.0.1 -p "${REDIS_PORT:-6379}" ping 2>/dev/null)" != "PONG" ]; then
      echo "Embedded Redis is RUNNING but not responding to PING (loading or wedged)"
      exit 1
    fi
  fi
else
  echo "Embedded Redis check skipped (disabled or external REDIS_HOST)"
fi

# Check embedded CrowdSec only when the AIO runs it (mirror the entrypoint gate:
# USE_CROWDSEC=yes and a local CROWDSEC_API). Otherwise a crash-looped embedded
# CrowdSec parks in supervisor FATAL while the container still reports healthy.
if [ "${USE_CROWDSEC:-no}" = "yes" ] && [[ "${CROWDSEC_API:-http://127.0.0.1:8000}" == http://127.0.0.1* || "${CROWDSEC_API:-http://127.0.0.1:8000}" == http://localhost* ]]; then
  status=$(supervisorctl status "crowdsec" 2>/dev/null)
  if ! echo "$status" | grep -q "RUNNING"; then
    echo "Embedded CrowdSec is enabled (USE_CROWDSEC=yes) but not running: $status"
    exit 1
  fi
else
  echo "Embedded CrowdSec check skipped (disabled or external CROWDSEC_API)"
fi

# Everything is fine
echo "All enabled services are healthy"
exit 0
