#!/bin/sh
#
# Maps BunkerWeb's NGINX-style LOG_LEVEL vocabulary (emerg alert crit error warn
# notice info debug) to the six levels Celery's --loglevel accepts (DEBUG INFO
# WARNING ERROR CRITICAL FATAL). Celery exits immediately on an unrecognized
# value, so this must run before the value ever reaches `celery ... --loglevel`.
#
# Usage: celery-loglevel.sh [value]   (echoes the mapped Celery level to stdout)

value="${1:-info}"
lower="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"

case "$lower" in
	emerg | alert | crit) echo "CRITICAL" ;;
	critical) echo "CRITICAL" ;;
	error) echo "ERROR" ;;
	warn | warning) echo "WARNING" ;;
	notice | info) echo "INFO" ;;
	debug) echo "DEBUG" ;;
	fatal) echo "FATAL" ;;
	*)
		echo "[WORKER] ⚠️ - Unknown LOG_LEVEL '${value}', defaulting Celery's loglevel to INFO" >&2
		echo "INFO"
		;;
esac
