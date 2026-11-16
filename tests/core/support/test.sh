#!/bin/bash
# Live `bwcli support` export: no credential may appear in the bundle.
#
# The bundle is produced inside the scheduler container (`docker exec <scheduler> bwcli support -o -`,
# the exact command the CLI's own refusal message gives for a container install) and inspected on
# the runner. Every secret below is either planted by the spec (a credential header in
# REVERSE_PROXY_HEADERS and CUSTOM_HEADER, a REDIS_PASSWORD) or injected by the harness itself (the
# API token, the API password): none of them may appear anywhere in any file of the bundle, with
# anonymization on and with --no-anonymize (credentials are always redacted, IPs and domains only
# when anonymizing).
#
# One mode per call: `default` (anonymized), `plain` (--no-anonymize).

set -Eeuo pipefail

if [ "${1:-}" != "docker" ]; then
	echo "support supports only the docker integration" >&2
	exit 1
fi
mode="${2:-}"
scheduler="${BW_TEST_SCHEDULER:-bw-scheduler}"

secrets=(
	"integ-bearer-7f3c9a"
	"integ-customkey-91ab"
	"integ-redis-pw-5d2e"
	"tests-secret-token"
	"P@ssw0rd"
)

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

case "$mode" in
default) extra=() ;;
plain) extra=(--no-anonymize) ;;
*)
	echo "support: unknown mode '${mode}'" >&2
	exit 1
	;;
esac

fail() {
	echo "support ${mode}: $*" >&2
	exit 1
}

# `-o -` writes the zip to stdout; stderr is kept apart so a log line never lands in the archive.
docker exec "$scheduler" bwcli support -o - "${extra[@]}" >"$tmp/bundle.zip" 2>"$tmp/stderr.txt" || fail "bwcli support failed: $(cat "$tmp/stderr.txt")"

# The bundle holds no credential once the check below passes, so it can be kept as evidence.
if [ -n "${BW_SUPPORT_BUNDLE_DIR:-}" ]; then
	mkdir -p "$BW_SUPPORT_BUNDLE_DIR"
	cp "$tmp/bundle.zip" "$BW_SUPPORT_BUNDLE_DIR/bundle-${mode}.zip"
fi

python3 -I - "$tmp/bundle.zip" "$mode" "${secrets[@]}" <<'PY'
import json
import sys
import zipfile

path, mode, *secrets = sys.argv[1:]
with zipfile.ZipFile(path) as bundle:
    assert bundle.testzip() is None, "corrupt zip"
    names = bundle.namelist()
    for required in ("manifest.json", "environment.json", "config.json", "plugins.json"):
        assert required in names, f"{required} missing from the bundle: {names}"
    contents = {name: bundle.read(name).decode("utf-8", "replace") for name in names}

manifest = json.loads(contents["manifest.json"])
print("files:", ", ".join(sorted(names)))
print("unavailable:", json.dumps(manifest.get("unavailable", [])))

leaks = [(name, secret) for name, text in contents.items() for secret in secrets if secret in text]
assert not leaks, f"credentials in the bundle: {leaks}"

config = contents["config.json"]
# The planted settings must be in the export (redacted), or the check above proves nothing.
for key in ("REVERSE_PROXY_HEADERS", "CUSTOM_HEADER", "REDIS_PASSWORD"):
    assert key in config, f"{key} is not in config.json, the probe would pass vacuously"

# ... and redacted, not dropped: the marker is what stands in for each value.
config_json = json.loads(config)
for key in ("REVERSE_PROXY_HEADERS", "CUSTOM_HEADER", "REDIS_PASSWORD"):
    entries = {name: value for name, value in config_json.items() if name == key or name.endswith("_" + key)}
    assert entries, f"{key} is not a key of config.json: {sorted(config_json)[:20]}"
    for name, value in entries.items():
        assert "[REDACTED]" in json.dumps(value), f"{name} is in config.json but not redacted: {value}"

# Non-secret material survives, and anonymization only touches domains and IPs.
domain_present = any("www.example.com" in text for text in contents.values())
if mode == "default":
    assert not domain_present, "the service domain is not anonymized"
else:
    assert domain_present, "--no-anonymize must keep the service domain"
print(f"support {mode}: all checks passed")
PY
