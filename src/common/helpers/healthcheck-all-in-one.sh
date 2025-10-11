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

# Everything is fine
echo "All enabled services are healthy"
exit 0
