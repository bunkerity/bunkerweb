"""Service pages render a stored secret as a placeholder, and the save puts it back (M35, FIX-C's
request to FIX-G).

`/services/<svc>` (and its plugin and template pages) rendered `type: password` values such as
AUTH_BASIC_PASSWORD into the page source. The render now masks them with FIX-C's
`models/secret_settings.py`, and `update_service` restores an untouched placeholder -- always both:
masking alone would SAVE the placeholder as the password.

Loader: `test_service_new_name_feedback.py`'s.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_service_new_name_feedback import MODULE, _FakeData  # noqa: E402

from app.models.secret_settings import SECRET_PLACEHOLDER  # noqa: E402

SETTINGS = {"AUTH_BASIC_PASSWORD": {"type": "password"}, "AUTH_BASIC_USER": {"type": "text"}}


def _update(monkeypatch, posted, *, service="app.example.com", clone="", stored_password="s3cret"):
    api = Mock()
    stored = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}, "AUTH_BASIC_PASSWORD": {"value": stored_password, "method": "ui"}}
    api.get_service.return_value = stored
    api.get_global_settings.return_value = {
        "SERVER_NAME": {"value": "app.example.com", "method": "ui"},
        "AUTH_BASIC_PASSWORD": {"value": "", "method": "default"},
    }
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = SETTINGS
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("edited", 0)
    bw_config.new_service.return_value = ("created", 0)
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)
    MODULE.update_service(service, posted, False, "easy", clone, {})
    return bw_config.check_variables.call_args.args[0]


def test_an_untouched_placeholder_keeps_the_stored_secret(monkeypatch):
    saved = _update(monkeypatch, {"SERVER_NAME": "app.example.com", "AUTH_BASIC_PASSWORD": SECRET_PLACEHOLDER, "AUTH_BASIC_USER": "bob"})
    assert saved["AUTH_BASIC_PASSWORD"] == "s3cret"


def test_a_typed_secret_replaces_it(monkeypatch):
    saved = _update(monkeypatch, {"SERVER_NAME": "app.example.com", "AUTH_BASIC_PASSWORD": "n3w", "AUTH_BASIC_USER": "bob"})
    assert saved["AUTH_BASIC_PASSWORD"] == "n3w"


def test_a_clone_keeps_the_source_secret(monkeypatch):
    """/services/new?clone=src renders the SOURCE's config, so its placeholder stands for the source's
    secret, not the global (empty) one."""
    saved = _update(
        monkeypatch,
        {"SERVER_NAME": "copy.example.com", "AUTH_BASIC_PASSWORD": SECRET_PLACEHOLDER},
        service="new",
        clone="app.example.com",
    )
    assert saved["AUTH_BASIC_PASSWORD"] == "s3cret"


def test_every_service_render_masks_the_config():
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "services.py").read_text(encoding="utf-8")
    for template in ("service_settings.html", "plugin_settings_page.html", "template_settings_page.html"):
        call = source[source.index(f'"{template}",') :]
        call = call[: call.index("\n    )")]
        assert "config=redact_secrets(" in call, f"{template} renders the raw config"
