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

	# shellcheck disable=SC2086 # intentional splitting for comma-separated values
	for raw in $(printf '%s' "${HIDE_SERVICE_LOGS//,/ }"); do
		if [ "$(normalize_log_key "$raw")" = "$match_key" ]; then
			return 0
		fi
	done

	return 1
}
