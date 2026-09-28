#!/bin/bash

normalize_log_key() {
	local value="$1"
	value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
	printf '%s' "$value" | tr -d '[:space:]'
}

hide_service_logs_match() {
	local service_key="$1"
	local match_key
	match_key="$(normalize_log_key "$service_key")"

	if [ -z "${HIDE_SERVICE_LOGS:-}" ]; then
		return 1
	fi

	# Disable pathname expansion around the word split so a crafted value like "*" can't
	# match against files in the wrapper's working directory. Restore the previous state
	# on every exit path.
	local _restore_f=1
	case $- in *f*) _restore_f=0 ;; esac
	set -f

	# shellcheck disable=SC2086 # intentional splitting for comma-separated values
	for raw in $(printf '%s' "${HIDE_SERVICE_LOGS//,/ }"); do
		if [ "$(normalize_log_key "$raw")" = "$match_key" ]; then
			[ "$_restore_f" = 1 ] && set +f
			return 0
		fi
	done

	[ "$_restore_f" = 1 ] && set +f
	return 1
}
