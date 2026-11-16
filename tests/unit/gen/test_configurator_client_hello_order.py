"""ClientHello order declarations survive loading a plugin manifest."""

import json
import logging

from Configurator import Configurator  # type: ignore


def test_client_hello_order_survives_manifest_loading(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    core = tmp_path / "core"
    plugin_dir = core / "hello"
    plugin_dir.mkdir(parents=True)
    order = {"ssl_client_hello": {"before": ["*"]}}
    manifest = {"id": "hello", "name": "Hello", "description": "TLS hook", "version": "1.0", "stream": "no", "settings": {}, "order": order}
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

    configurator = Configurator(str(settings), str(core), [], [], {}, logging.getLogger("cfg-client-hello-test"))

    assert configurator.get_plugins("core")[0]["order"] == order
