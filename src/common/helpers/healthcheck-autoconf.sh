#!/bin/bash

BASE=/var/tmp/bunkerweb/autoconf.healthy
EXPECTED="${BASE}.expected"

# Docker/Swarm mode, and Kubernetes mode before the controller has published its
# per-watch markers, rely on this single legacy marker written by main.py.
if [ ! -f "$BASE" ] ; then
	exit 1
fi

# Kubernetes mode: every watch this run started must have its own marker, or a
# watch stuck retrying could hide behind a sibling watch that is still streaming
# and marking the shared file healthy. Every marker is seeded at process start
# (present is the default; only an exhausted watch removes its own), so presence
# alone is the right check here, not an mtime-based staleness window that would
# fail a watch that is healthy but simply has nothing to report yet.
if [ -f "$EXPECTED" ] ; then
	mapfile -t watch_types < "$EXPECTED"
	for watch_type in "${watch_types[@]}" ; do
		[ -z "$watch_type" ] && continue
		if [ ! -f "${BASE}.${watch_type}" ] ; then
			exit 1
		fi
	done
fi

exit 0
