"""CROWDSEC_CACHE_SIZE and CROWDSEC_METADATA_CACHE_SIZE: rendered into the nginx shared dicts, bad values refused.

The shared dict lines are read from `nginx -T` of the running instance (the rendered configuration the instance
actually loaded), the validation from the API's setting validator (the Configurator regex the scheduler applies).
"""

import subprocess
import sys

import requests

API = "http://127.0.0.1:8888"
AUTH = ("admin", "P@ssw0rd")


def fail(message):
    print(f"crowdsec-cache-size: {message}", file=sys.stderr)
    sys.exit(1)


dump = subprocess.run(
    ["docker", "exec", "bunkerweb", "nginx", "-T", "-e", "/var/log/bunkerweb/error.log", "-c", "/etc/nginx/nginx.conf"],
    text=True,
    capture_output=True,
    timeout=60,
    check=False,
)
text = dump.stdout + dump.stderr
lines = [line.strip() for line in text.splitlines() if "lua_shared_dict crowdsec_" in line]
print("SHARED_DICT_LINES", lines, flush=True)
for expected in ("lua_shared_dict crowdsec_cache 50m;", "lua_shared_dict crowdsec_metadata 12m;"):
    if expected not in lines:
        fail(f"{expected!r} not in the rendered configuration: {lines}")


def valid(setting, value):
    response = requests.post(f"{API}/global_settings/validate", auth=AUTH, json={"setting": setting, "value": value}, timeout=30)
    print(setting, repr(value), response.status_code, response.text[:200], flush=True)
    if response.status_code != 200:
        fail(f"validator answered {response.status_code}")
    return response.json()["valid"]


for setting in ("CROWDSEC_CACHE_SIZE", "CROWDSEC_METADATA_CACHE_SIZE"):
    for good in ("1m", "24m", "100M"):
        if not valid(setting, good):
            fail(f"{setting}={good!r} must be accepted")
    for bad in ("", "0m", "100", "1g", "1.5m", "-1m", "10 m", "m"):
        if valid(setting, bad):
            fail(f"{setting}={bad!r} must be refused")
print("CROWDSEC_CACHE_SIZE_OK")
