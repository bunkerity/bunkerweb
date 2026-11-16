"""The loading configuration keeps the IPv6 settings, so an IPv6-only stack can start before the first push.

Both shipped startup scripts run against a temporary root (see ``_startup_sandbox``); the settings they hand to
the generator are read back from the startup env file they write.
"""

import json
import os
import signal

import pytest
from _startup_sandbox import ROOT, Sandbox

IPV6 = {"USE_IPV6": "yes", "API_LISTEN_IP": "::", "DNS_RESOLVERS": "[2001:db8::53]:5353"}
DEFAULTS = {"docker": {"USE_IPV6": "no", "API_LISTEN_IP": "0.0.0.0", "DNS_RESOLVERS": "127.0.0.11"}, "linux": {"USE_IPV6": "no"}}


def _startup_env(tmp_path, variant, *, env=None, config=""):
    box = Sandbox(tmp_path, variant)
    box.keep_a_config()
    (box.root / "ctl/keep").write_text("no")
    (box.root / "etc/bunkerweb/variables.env").write_text("KEEP_CONFIG_ON_RESTART=no\n" + config)
    process = box.start(env)
    try:
        box.wait_for(lambda: box.pid_file.exists())
        settings = box.startup_env
    finally:
        if box.pid_file.exists():
            if variant == "docker":
                os.kill(process.pid, signal.SIGTERM)
            else:
                box.stop_nginx()
        box.finish(process)
    return settings


@pytest.mark.parametrize("variant", ["docker", "linux"])
@pytest.mark.parametrize("key", IPV6)
def test_ipv6_process_settings_reach_the_startup_env(tmp_path, variant, key):
    settings = _startup_env(tmp_path, variant, env=IPV6)
    assert settings.get(key) == IPV6[key], settings


def test_linux_ipv6_file_settings_reach_the_startup_env(tmp_path):
    config = "".join(f"{key}={value}\n" for key, value in IPV6.items())
    settings = _startup_env(tmp_path, "linux", config=config)
    for key, value in IPV6.items():
        assert settings.get(key) == value, settings


@pytest.mark.parametrize("variant", ["docker", "linux"])
@pytest.mark.parametrize("empty", [False, True], ids=["unset", "empty"])
def test_defaults_are_the_documented_ones(tmp_path, variant, empty):
    defaults = json.loads((ROOT / "src/common/settings.json").read_text(encoding="utf-8"))
    assert {key: defaults[key]["default"] for key in IPV6} == {"USE_IPV6": "no", "API_LISTEN_IP": "0.0.0.0", "DNS_RESOLVERS": "127.0.0.11"}
    settings = _startup_env(tmp_path, variant, env=dict.fromkeys(IPV6, "") if empty else None)
    for key, value in DEFAULTS[variant].items():
        assert settings.get(key) == value, settings
