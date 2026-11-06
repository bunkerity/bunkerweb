#!/bin/bash

# prerm and %preun run while the unit files and ExecStop wrappers still exist.
case "${1:-}" in
    remove|0) ;;
    *) exit 0 ;;
esac

if command -v systemctl >/dev/null 2>&1; then
    for service in bunkerweb bunkerweb-scheduler bunkerweb-ui bunkerweb-api; do
        if ! systemctl stop "$service"; then
            echo "❌ Could not stop $service; aborting removal." >&2
            exit 1
        fi
        if ! systemctl disable "$service"; then
            echo "❌ Could not disable $service; aborting removal." >&2
            exit 1
        fi
    done
fi
