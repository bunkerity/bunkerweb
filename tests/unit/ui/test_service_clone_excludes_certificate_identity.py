"""QA-UI N-M3: cloning a service must not carry the SOURCE's certificate identity onto the new
one.

``update_service``'s clone loop (``routes/services.py``) copied every setting the source service
had a value for, prefix included. Two shapes of that were wrong:

* ``SELF_SIGNED_SSL_SUBJ`` is a literal ``/CN=.../`` string, never derived from the clone's own
  ``SERVER_NAME`` -- copying it verbatim baked the source's domain into the clone's self-signed
  certificate. Reproduced live: cloning ``www.example.com`` as ``qa5-clone.example.com`` created a
  certificate named ``qa5-clone.example.com`` with CN ``www.example.com``, which survived the
  clone's own deletion because nothing owned it as a certificate row.
* ``CUSTOM_SSL_CERT``/``CUSTOM_SSL_KEY``/``CUSTOM_SSL_CERT_DATA``/``CUSTOM_SSL_KEY_DATA`` are the
  source's actual certificate and private key (a path, or the file content) -- copying those would
  serve the clone under a hostname the certificate was never issued for, and hand it the source's
  private key besides.

An ordinary setting (``GENERATE_SELF_SIGNED_SSL``) must still be cloned -- only certificate-identity
settings are excluded, not everything the source customized.

Same loader idiom as ``test_service_save_flash_type.py``.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]


def _import_services_module():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.CORE_PLUGINS_PATH = REPO_ROOT / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._services_test_clone_cert_identity"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_services_module()


class _FakeData(dict):
    def load_from_file(self):
        pass


def test_certificate_identity_settings_are_not_cloned(monkeypatch):
    source_config = {
        "SERVER_NAME": "www.example.com",
        "GENERATE_SELF_SIGNED_SSL": "yes",
        "SELF_SIGNED_SSL_SUBJ": "/CN=www.example.com/",
        "USE_CUSTOM_SSL": "yes",
        "CUSTOM_SSL_CERT": "/path/to/www.example.com.pem",
        "CUSTOM_SSL_KEY": "/path/to/www.example.com.key",
        "CUSTOM_SSL_CERT_DATA": "SOURCE-CERT-BASE64",
        "CUSTOM_SSL_KEY_DATA": "SOURCE-KEY-BASE64",
    }

    api = Mock()
    api.get_service.return_value = source_config
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    api.get_global_settings.return_value = {}

    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = {}
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.new_service.return_value = ("Configuration successfully created for service qa5-clone.example.com.", 0)

    data = _FakeData(TO_FLASH=[])
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", data)
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)

    posted = {"SERVER_NAME": "qa5-clone.example.com", "USE_UI": "no"}
    MODULE.update_service("new", posted, False, "easy", "www.example.com", {})

    assert bw_config.new_service.called, "new_service was never reached -- this test proves nothing"
    saved_variables = bw_config.new_service.call_args.args[0]

    # An ordinary cloned setting still carries over.
    assert saved_variables.get("GENERATE_SELF_SIGNED_SSL") == "yes"
    assert saved_variables.get("USE_CUSTOM_SSL") == "yes"

    # The source's certificate identity must not.
    for excluded in ("SELF_SIGNED_SSL_SUBJ", "CUSTOM_SSL_CERT", "CUSTOM_SSL_KEY", "CUSTOM_SSL_CERT_DATA", "CUSTOM_SSL_KEY_DATA"):
        assert (
            excluded not in saved_variables or saved_variables[excluded] != source_config[excluded]
        ), f"{excluded} was copied from the clone source: {saved_variables.get(excluded)!r}"
    assert saved_variables["SERVER_NAME"] == "qa5-clone.example.com"
