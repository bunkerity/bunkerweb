"""RAW-editor setting drafts (1.6.15 #3631, ported to 1.7).

A setting draft is a stored value that is NEVER rendered: ``bw_global_values.is_draft`` /
``bw_services_settings.is_draft`` keep the value while the inherited (global), template or plugin
default applies. It is a different thing from a draft SERVICE (``bw_services.is_draft``): a live
service can hold a drafted setting, and a draft service's settings are not drafts.

Only the RAW editor changes that state, through ``save_config(draft_settings=...)``: ``True``
drafts a key, ``False`` activates it, ``None`` deletes the drafted row. Every other writer — the
composition editor, the API, autoconf, the scheduler's env pass — sends no map and must leave a
drafted row exactly as it is, neither rewriting nor deleting it.
"""

import pytest

from fixtures.seed import make_core_plugin, make_general_settings, session
from model import Global_values, Services_settings

pytestmark = pytest.mark.slow

SERVICE = "app.example.com"


def _settings():
    return {
        "ALPHA_FLAG": {"id": "alpha-flag", "context": "multisite", "default": "no", "help": "h", "label": "L", "regex": "^(yes|no)$", "type": "check"},
        "ALPHA_MODE": {"id": "alpha-mode", "context": "multisite", "default": "off", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
        "ALPHA_GLOBAL": {"id": "alpha-global", "context": "global", "default": "def", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
    }


def _general():
    return make_general_settings() | {
        "USE_TEMPLATE": {
            "id": "use-template",
            "context": "multisite",
            "default": "",
            "help": "h",
            "label": "T",
            "regex": "^.*$",
            "type": "multivalue",
            "separator": " ",
        }
    }


@pytest.fixture
def seeded(db):
    db.init_tables([_general(), make_core_plugin("alpha", settings=_settings())])
    db.initialize_db("1.7.0", "Docker")
    return db


def _multisite(extra=None):
    return {"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_SERVER_NAME": SERVICE} | (extra or {})


def _rows(db):
    with session(db) as s:
        return {
            "global": {(r.setting_id, r.suffix or 0): (r.value, r.method, bool(r.is_draft)) for r in s.query(Global_values).all()},
            "service": {(r.service_id, r.setting_id, r.suffix or 0): (r.value, r.method, bool(r.is_draft)) for r in s.query(Services_settings).all()},
        }


def _save(db, config, method="ui", **kwargs):
    result = db.save_config(config, method, **kwargs)
    assert isinstance(result, set), result
    return result


class TestGlobalDraft:
    def test_a_global_draft_is_stored_but_never_rendered(self, seeded):
        _save(seeded, _multisite({"ALPHA_FLAG": "yes"}), draft_settings={"ALPHA_FLAG": True})

        assert _rows(seeded)["global"][("ALPHA_FLAG", 0)] == ("yes", "ui", True)
        config = seeded.get_config()
        assert config["ALPHA_FLAG"] == "no"
        # A service inherits the effective global, never the draft's retained value.
        assert config[f"{SERVICE}_ALPHA_FLAG"] == "no"

    def test_the_raw_view_sees_the_draft_and_flags_it(self, seeded):
        _save(seeded, _multisite({"ALPHA_FLAG": "yes"}), draft_settings={"ALPHA_FLAG": True})

        raw = seeded.get_config(methods=True, with_setting_drafts=True)
        assert raw["ALPHA_FLAG"]["value"] == "yes"
        assert raw["ALPHA_FLAG"]["is_draft"] is True
        # ... while the service inherits the effective value, marked live.
        assert raw[f"{SERVICE}_ALPHA_FLAG"]["value"] == "no"
        assert not raw[f"{SERVICE}_ALPHA_FLAG"].get("is_draft")

    def test_activating_a_draft_makes_it_live(self, seeded):
        _save(seeded, _multisite({"ALPHA_FLAG": "yes"}), draft_settings={"ALPHA_FLAG": True})
        _save(seeded, _multisite({"ALPHA_FLAG": "yes"}), draft_settings={"ALPHA_FLAG": False})

        assert _rows(seeded)["global"][("ALPHA_FLAG", 0)] == ("yes", "ui", False)
        assert seeded.get_config()["ALPHA_FLAG"] == "yes"

    def test_a_draft_of_a_never_set_setting_at_its_default_is_kept(self, seeded):
        """cf76f5bb7e: drafting a line that still shows the plugin default must store a row; the
        usual "default value -> no row" rule would silently drop the draft."""
        _save(seeded, _multisite({"ALPHA_MODE": "off"}), draft_settings={"ALPHA_MODE": True})

        assert _rows(seeded)["global"][("ALPHA_MODE", 0)] == ("off", "ui", True)

    def test_none_deletes_a_draft_the_payload_no_longer_carries(self, seeded):
        _save(seeded, _multisite({"ALPHA_FLAG": "yes"}), draft_settings={"ALPHA_FLAG": True})
        _save(seeded, _multisite(), draft_settings={"ALPHA_FLAG": None})

        assert ("ALPHA_FLAG", 0) not in _rows(seeded)["global"]

    def test_the_non_multisite_pass_honours_drafts_too(self, seeded):
        """``PATCH /global_settings`` and every single-site save land in this pass."""
        _save(seeded, {"ALPHA_GLOBAL": "staged"}, skip_service_management=True, draft_settings={"ALPHA_GLOBAL": True})

        assert _rows(seeded)["global"][("ALPHA_GLOBAL", 0)] == ("staged", "ui", True)
        assert seeded.get_config(global_only=True)["ALPHA_GLOBAL"] == "def"


class TestServiceDraft:
    def test_a_draft_on_a_live_service_renders_the_inherited_value(self, seeded):
        _save(seeded, _multisite({"ALPHA_MODE": "detect", f"{SERVICE}_ALPHA_MODE": "block"}), draft_settings={f"{SERVICE}_ALPHA_MODE": True})

        assert _rows(seeded)["service"][(SERVICE, "ALPHA_MODE", 0)] == ("block", "ui", True)
        assert seeded.get_config()[f"{SERVICE}_ALPHA_MODE"] == "detect"
        # The service itself stays live: a setting draft is not a service draft.
        assert SERVICE in seeded.get_config()["SERVER_NAME"].split()

    def test_a_drafted_key_falls_back_through_every_template_layer(self, seeded):
        """1.7's USE_TEMPLATE is an ordered list: the fallback of a drafted key is the last layer
        that declares it, not the plugin default and not 1.6.15's single template."""
        assert seeded.create_template("low", name="Low", settings={"ALPHA_MODE": "low-mode"}, steps=[{"title": "S", "settings": ["ALPHA_MODE"]}]) == ""
        assert seeded.create_template("high", name="High", settings={"ALPHA_MODE": "high-mode"}, steps=[{"title": "S", "settings": ["ALPHA_MODE"]}]) == ""
        _save(
            seeded,
            _multisite({f"{SERVICE}_USE_TEMPLATE": "low high", f"{SERVICE}_ALPHA_MODE": "staged"}),
            draft_settings={f"{SERVICE}_ALPHA_MODE": True},
        )

        assert _rows(seeded)["service"][(SERVICE, "ALPHA_MODE", 0)] == ("staged", "ui", True)
        assert seeded.get_config()[f"{SERVICE}_ALPHA_MODE"] == "high-mode"

    def test_use_template_and_server_name_can_never_be_drafted(self, seeded):
        _save(
            seeded,
            _multisite({f"{SERVICE}_USE_TEMPLATE": ""}),
            draft_settings={f"{SERVICE}_SERVER_NAME": True, f"{SERVICE}_USE_TEMPLATE": True, "MULTISITE": True},
        )

        rows = _rows(seeded)
        assert not any(is_draft for *_, is_draft in rows["global"].values())
        assert not any(is_draft for *_, is_draft in rows["service"].values())
        assert SERVICE in seeded.get_config()["SERVER_NAME"].split()


class TestOtherWritersLeaveDraftsAlone:
    """The cleanup guard and the opaque-row rule: a save that carries no draft map is not
    allowed to see a drafted row at all."""

    @pytest.fixture
    def drafted(self, seeded):
        _save(
            seeded,
            _multisite({"ALPHA_FLAG": "yes", f"{SERVICE}_ALPHA_MODE": "block"}),
            draft_settings={"ALPHA_FLAG": True, f"{SERVICE}_ALPHA_MODE": True},
        )
        return seeded

    def test_a_composition_save_that_omits_the_drafted_keys_keeps_them(self, drafted):
        _save(drafted, _multisite({f"{SERVICE}_ALPHA_FLAG": "no"}))

        rows = _rows(drafted)
        assert rows["global"][("ALPHA_FLAG", 0)] == ("yes", "ui", True)
        assert rows["service"][(SERVICE, "ALPHA_MODE", 0)] == ("block", "ui", True)

    def test_a_save_posting_the_effective_value_does_not_overwrite_the_draft(self, drafted):
        """The composition editor renders the effective value and posts it back unchanged."""
        _save(drafted, _multisite({"ALPHA_FLAG": "no", f"{SERVICE}_ALPHA_MODE": "off"}))

        rows = _rows(drafted)
        assert rows["global"][("ALPHA_FLAG", 0)] == ("yes", "ui", True)
        assert rows["service"][(SERVICE, "ALPHA_MODE", 0)] == ("block", "ui", True)

    def test_the_scheduler_env_pass_leaves_drafts_alone(self, drafted):
        """The first-start path CLOSE-E2 left unverified: the env save runs as ``scheduler`` with
        its own explicit keys, and must neither rewrite nor delete a UI draft."""
        _save(drafted, _multisite({"ALPHA_FLAG": "no"}), method="scheduler", explicit_keys={"MULTISITE", "SERVER_NAME", "ALPHA_FLAG"})

        rows = _rows(drafted)
        assert rows["global"][("ALPHA_FLAG", 0)] == ("yes", "ui", True)
        assert rows["service"][(SERVICE, "ALPHA_MODE", 0)] == ("block", "ui", True)
