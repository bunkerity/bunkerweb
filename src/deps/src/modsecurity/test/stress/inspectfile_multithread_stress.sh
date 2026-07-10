#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
EXAMPLE_DIR="$REPO_ROOT/examples/multithread"
BIN="$EXAMPLE_DIR/multithread"
RULES="$EXAMPLE_DIR/inspectfile_rules.conf"
THREADS="${1:-60}"
ITERATIONS="${2:-120}"
TIMEOUT_SECS="${3:-90}"

if [ ! -x "$BIN" ]; then
  echo "stress-test: missing binary $BIN" >&2
  echo "build it first (e.g. make -C examples/multithread multithread)" >&2
  exit 2
fi

TMP_OUT=$(mktemp)
trap 'rm -f "$TMP_OUT"' EXIT

cd "$EXAMPLE_DIR"
set +e
if command -v timeout >/dev/null 2>&1; then
  timeout "$TIMEOUT_SECS" "$BIN" "$RULES" "$THREADS" "$ITERATIONS" >"$TMP_OUT" 2>&1
else
  echo "stress-test: warning: 'timeout' command not found, running without timeout" >&2
  "$BIN" "$RULES" "$THREADS" "$ITERATIONS" >"$TMP_OUT" 2>&1
fi
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ]; then
  echo "stress-test: process exit status=$STATUS" >&2
  cat "$TMP_OUT" >&2
  exit "$STATUS"
fi

EXPECTED="completed_threads=$THREADS"
if ! grep -q "$EXPECTED" "$TMP_OUT"; then
  echo "stress-test: missing expected marker: $EXPECTED" >&2
  cat "$TMP_OUT" >&2
  exit 3
fi

if grep -q "open_fds_before=" "$TMP_OUT" && grep -q "open_fds_after=" "$TMP_OUT"; then
  BEFORE=$(grep 'open_fds_before=' "$TMP_OUT" | tail -n1 | cut -d= -f2)
  AFTER=$(grep 'open_fds_after=' "$TMP_OUT" | tail -n1 | cut -d= -f2)
  DELTA=$((AFTER - BEFORE))
  echo "fd_delta=$DELTA"
fi

echo "stress-test: ok"
cat "$TMP_OUT"
