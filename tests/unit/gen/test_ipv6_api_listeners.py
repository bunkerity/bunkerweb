"""Internal API listeners format IPv6 authorities without changing loopback access."""

import logging
import os.path
from pathlib import Path

import pytest

from Configurator import Configurator
import Templator as templator_module

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("host", ["2001:db8::1", "[2001:db8::1]", "::", "[::]", "127.0.0.1", "192.0.2.1"])
@pytest.mark.parametrize("tls,certificate", [(False, False), (True, False), (True, True)])
def test_api_listeners_bracket_ipv6(tmp_path, monkeypatch, host, tls, certificate):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(templator_module, "sep", str(tmp_path))
    config = Configurator(
        str(ROOT / "src/common/settings.json"),
        str(ROOT / "src/common/core"),
        str(plugins),
        str(plugins),
        {"API_LISTEN_IP": host, "API_LISTEN_HTTPS": "yes" if tls else "no"},
        logging.getLogger("ipv6-api-listeners"),
    ).get_config(None)
    assert config["API_LISTEN_IP"] == host
    templator = templator_module.Templator(
        str(ROOT / "src/common/confs"),
        str(ROOT / "src/common/core"),
        str(plugins),
        str(plugins),
        str(output),
        "/etc/nginx",
        config,
        config.copy(),
        config.copy(),
    )
    real_isfile = os.path.isfile
    monkeypatch.setattr("os.path.isfile", lambda path: certificate if str(path) == "/var/cache/bunkerweb/jobs/api-server-cert.pem" else real_isfile(path))
    assert templator._render_template("api.conf", {**templator._base_template_vars, **config, "all": config})
    text = (output / "api.conf").read_text()
    endpoint = f"[{host}]" if ":" in host and not host.startswith("[") else host
    assert f"listen {endpoint}:5000 reuseport;" in text
    assert text.count("listen 127.0.0.1:5000 reuseport;") == 1
    if tls:
        suffix = " ssl" if certificate else ""
        assert f"listen {endpoint}:5443{suffix} reuseport;" in text
        assert text.count(f"listen 127.0.0.1:5443{suffix} reuseport;") == 1
