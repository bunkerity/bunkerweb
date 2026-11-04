"""Bootstrap env keeps IPv6 overrides before the scheduler's first configuration push."""

import json

import pytest
from _t7_helpers import ROOT, bash, block, function, retarget, source

SCRIPTS = {"docker": "src/bw/entrypoint.sh", "linux": "src/linux/scripts/start.sh"}
IPV6 = {"USE_IPV6": "yes", "API_LISTEN_IP": "::", "DNS_RESOLVERS": "[2001:db8::53]:5353"}
# Pre-fix output, with the Linux-specific defaults substituted below.
PREVIOUS_DEFAULT_OUTPUT = """IS_LOADING=yes
USE_BUNKERNET=no
SEND_ANONYMOUS_REPORT=no
SERVER_NAME=
MODSECURITY_CRS_VERSION=4
API_LISTEN_HTTP=yes
API_HTTP_PORT=5000
API_LISTEN_HTTPS=no
API_HTTPS_PORT=5443
API_SERVER_NAME=bwapi
API_WHITELIST_IP=127.0.0.0/8
API_TOKEN=
USE_REAL_IP=no
USE_PROXY_PROTOCOL=no
REAL_IP_FROM=192.168.0.0/16 172.16.0.0/12 10.0.0.0/8
REAL_IP_HEADER=X-Forwarded-For
HTTP_PORT=8080
HTTPS_PORT=8443
KEEP_CONFIG_ON_RESTART=no
"""


def _run(tmp_path, variant, *, env=None, config=""):
    text = source(SCRIPTS[variant])
    script = function(text, "generate_tmp_env_content")
    if variant == "linux":
        env_file = tmp_path / "etc/bunkerweb/variables.env"
        env_file.parent.mkdir(parents=True)
        env_file.write_text(config, encoding="utf-8")
        loading = block(text, r"^    declare -A defaults=\(.*?(?=^    tmp_env_path=)", "the defaults and config loading block")
        script += retarget(loading, tmp_path, "/etc/bunkerweb")
    result = bash(script + "\ngenerate_tmp_env_content\n", env={"PATH": "/usr/bin:/bin", **(env or {})})
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("variant", SCRIPTS)
@pytest.mark.parametrize("key", IPV6)
def test_ipv6_process_settings_reach_bootstrap_env(tmp_path, variant, key):
    output = _run(tmp_path, variant, env=IPV6)
    settings = dict(line.split("=", 1) for line in output.splitlines())
    assert settings.get(key) == IPV6[key], f"bootstrap lost {key}: {output}"


def test_linux_ipv6_file_settings_reach_bootstrap_env(tmp_path):
    output = _run(tmp_path, "linux", config="USE_IPV6=yes\nAPI_LISTEN_IP=::\nDNS_RESOLVERS=[2001:db8::53]:5353\n")
    settings = dict(line.split("=", 1) for line in output.splitlines())
    for key, value in IPV6.items():
        assert settings.get(key) == value, f"bootstrap ignored configured {key}: {output}"


@pytest.mark.parametrize("variant", SCRIPTS)
@pytest.mark.parametrize("empty", [False, True], ids=["unset", "empty"])
def test_bootstrap_defaults_preserve_previous_output(tmp_path, variant, empty):
    output = _run(tmp_path, variant, env=dict.fromkeys(IPV6, "") if empty else {})
    defaults = json.loads((ROOT / "src/common/settings.json").read_text(encoding="utf-8"))
    assert {key: defaults[key]["default"] for key in IPV6} == {
        "USE_IPV6": "no",
        "API_LISTEN_IP": "0.0.0.0",
        "DNS_RESOLVERS": "127.0.0.11",
    }
    if variant == "docker":
        additions = "USE_IPV6=no\nAPI_LISTEN_IP=0.0.0.0\nDNS_RESOLVERS=127.0.0.11\n"
        expected = PREVIOUS_DEFAULT_OUTPUT.replace("SERVER_NAME=\n", "SERVER_NAME=\n" + additions, 1)
    else:
        expected = PREVIOUS_DEFAULT_OUTPUT.replace("MODSECURITY_CRS_VERSION=4\n", "USE_IPV6=no\nDNS_RESOLVERS=9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4\n")
        expected = expected.replace("API_SERVER_NAME=", "API_LISTEN_IP=127.0.0.1\nAPI_SERVER_NAME=", 1)
        expected = expected.replace("HTTP_PORT=8080\n", "HTTP_PORT=80\n").replace("HTTPS_PORT=8443\n", "HTTPS_PORT=443\n")
    assert output == expected
