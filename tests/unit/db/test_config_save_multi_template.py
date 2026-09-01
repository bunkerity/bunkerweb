"""Integration tier — save_config's NON-MULTISITE pass against a MULTI-LAYER ``USE_TEMPLATE``.

``USE_TEMPLATE`` is an ordered list ("low high"), and the non-multisite pass used to feed that
RAW string to ``filter_by(template_id=...)``. With two layers it matched nothing, so every
template default silently fell back to the PLUGIN default. Three consequences, one test class
each: an explicit operator value equal to the plugin default was dropped (the template then won
at read time), a cleared list re-inherited the template's, and the template's own values were
written into ``bw_global_values`` as operator-set rows.

The multisite branch has always been correct (``split_templates`` + ``merge_template_settings``);
these tests pin the same semantics — union across layers, last-wins on a collision — on the
non-multisite side.
"""

import pytest

from fixtures.seed import make_core_plugin, make_general_settings, session
from model import Global_values, Services

pytestmark = pytest.mark.slow


def _text(setting_id, ctx, *, default="", multiple=None):
    out = {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": "^.*$", "type": "text"}
    if multiple:
        out["multiple"] = multiple
    return out


def _settings():
    return {
        # plugin default "no" -- the value an operator turning the feature back OFF sends.
        "ALPHA_FLAG": {"id": "alpha-flag", "context": "global", "default": "no", "help": "h", "label": "L", "regex": "^(yes|no)$", "type": "check"},
        # plugin default "" -- the fail-open direction: clearing a list writes the plugin default.
        "ALPHA_LIST": {
            "id": "alpha-list",
            "context": "global",
            "default": "",
            "help": "h",
            "label": "L",
            "regex": r"^( *([a-z0-9.]+) *)*$",
            "type": "multivalue",
            "separator": " ",
        },
        # declared by BOTH layers with different values -- the last-wins probe.
        "ALPHA_MODE": _text("alpha-mode", "global", default="off"),
        # a multiple-group member, to pin the suffixed-slot half of the fix.
        "ALPHA_URL": _text("alpha-url", "global", default="", multiple="alpha-urls"),
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
def layered(db):
    """Two template layers, both real, disagreeing on exactly one setting.

    ``low`` alone would make several of these tests pass under the bug (a single id matches the
    raw filter), which is why every one of them applies BOTH layers.
    """
    db.init_tables([_general(), make_core_plugin("alpha", settings=_settings())])
    db.initialize_db("1.7.0", "Docker")
    assert (
        db.create_template(
            "low",
            name="Low",
            settings={"ALPHA_FLAG": "yes", "ALPHA_LIST": "10.0.0.1 10.0.0.2", "ALPHA_MODE": "detect", "ALPHA_URL_1": "http://backend1"},
            steps=[{"title": "S", "settings": ["ALPHA_FLAG", "ALPHA_LIST", "ALPHA_MODE", "ALPHA_URL_1"]}],
        )
        == ""
    )
    assert (
        db.create_template(
            "high",
            name="High",
            settings={"ALPHA_MODE": "block", "SERVER_NAME": "tmpl.example.com"},
            steps=[{"title": "S", "settings": ["ALPHA_MODE", "SERVER_NAME"]}],
        )
        == ""
    )
    return db


def _global_rows(db):
    with session(db) as s:
        return {(r.setting_id, r.suffix or 0): (r.value, r.method) for r in s.query(Global_values).all()}


class TestExplicitValueSurvivesTwoLayers:
    """Facet 1 -- the operator's explicit value must beat the template, even when it happens to
    equal the plugin default."""

    def test_explicit_off_equal_to_the_plugin_default_is_persisted_on_a_fresh_save(self, layered):
        # FRESH save: no earlier single-layer save has stored a row for ALPHA_FLAG, so nothing
        # shields it -- config_read's "a non-default method skips the layer" gate only helps once
        # a row exists. This is the run shape the defect actually bites in.
        assert _global_rows(layered).get(("ALPHA_FLAG", 0)) is None

        result = layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_FLAG": "no"}, "scheduler", skip_service_management=True)

        assert isinstance(result, set), result
        assert _global_rows(layered)[("ALPHA_FLAG", 0)] == ("no", "scheduler")
        assert layered.get_config()["ALPHA_FLAG"] == "no"

    def test_a_single_layer_behaves_identically(self, layered):
        """The acceptance bar: the one-layer path was never broken and must not move."""
        layered.save_config({"USE_TEMPLATE": "low", "ALPHA_FLAG": "no"}, "scheduler", skip_service_management=True)
        assert layered.get_config()["ALPHA_FLAG"] == "no"

    def test_the_layers_are_folded_last_wins_not_first_wins(self, layered):
        """``low`` says detect, ``high`` says block. Only the LAST layer is the effective default:
        sending it is a no-op, sending the shadowed one is a real override."""
        layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_MODE": "block"}, "scheduler", skip_service_management=True)
        assert ("ALPHA_MODE", 0) not in _global_rows(layered)

        layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_MODE": "detect"}, "scheduler", skip_service_management=True)
        assert _global_rows(layered)[("ALPHA_MODE", 0)] == ("detect", "scheduler")
        assert layered.get_config()["ALPHA_MODE"] == "detect"


class TestClearedListDoesNotReinherit:
    """Facet 2 -- the FAIL-OPEN one. Most list defaults are "", so clearing a template-supplied
    allowlist writes a value equal to the plugin default."""

    def test_clearing_a_template_supplied_list_is_persisted(self, layered):
        result = layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_LIST": ""}, "scheduler", skip_service_management=True)

        assert isinstance(result, set), result
        assert _global_rows(layered)[("ALPHA_LIST", 0)] == ("", "scheduler")
        assert layered.get_config()["ALPHA_LIST"] == ""


class TestNoTemplateRowPollution:
    """Facet 3 -- the config handed to save_config already carries the template's resolved values
    (Configurator folds them in). They are the template's, not the operator's, and must not
    materialise as method="scheduler" rows the UI then shows as operator-set."""

    def test_the_templates_own_values_do_not_become_global_rows(self, layered):
        result = layered.save_config(
            {"USE_TEMPLATE": "low high", "ALPHA_FLAG": "yes", "ALPHA_LIST": "10.0.0.1 10.0.0.2", "ALPHA_MODE": "block"},
            "scheduler",
            skip_service_management=True,
        )

        assert isinstance(result, set), result
        rows = _global_rows(layered)
        assert ("ALPHA_FLAG", 0) not in rows
        assert ("ALPHA_LIST", 0) not in rows
        assert ("ALPHA_MODE", 0) not in rows

    def test_a_suffixed_member_at_the_templates_own_value_does_not_become_a_row(self, layered):
        """The slot half: a multiple-group slot kept alive by a template layer must not be
        persisted, or every template-declared slot lands as operator rows. ``high`` does not
        declare ALPHA_URL_1 at all -- the merge is a UNION of the layers, not just the last."""
        result = layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_URL_1": "http://backend1"}, "scheduler", skip_service_management=True)

        assert isinstance(result, set), result
        assert ("ALPHA_URL", 1) not in _global_rows(layered)


class TestServerNameFallback:
    """The third site: with no SERVER_NAME in the config, the service to create is read off the
    template layers."""

    def test_server_name_comes_from_the_layer_that_declares_it(self, layered):
        result = layered.save_config({"USE_TEMPLATE": "low high"}, "scheduler")

        assert isinstance(result, set), result
        with session(layered) as s:
            assert {row.id for row in s.query(Services).all()} == {"tmpl.example.com"}


class TestExistingRowUpdatePath:
    """The `elif should_update_value` branch -- the only path in this pass that DELETES an
    existing row. It compares against the same `nm_default`, so it moved with the fix and needs
    its own pins: one where the row must go, one where it must stay.
    """

    @staticmethod
    def _seed_row(db):
        # A value no layer declares, so it persists under a single layer (where the raw read
        # worked) and leaves a real operator-owned row for the second save to act on.
        assert isinstance(db.save_config({"USE_TEMPLATE": "low", "ALPHA_MODE": "custom"}, "scheduler", skip_service_management=True), set)
        assert _global_rows(db)[("ALPHA_MODE", 0)] == ("custom", "scheduler")

    def test_editing_down_to_the_effective_template_value_removes_the_row(self, layered):
        """ "block" is what `low high` resolves to, so storing it would be a template value wearing
        an operator's method -- the row must go and the overlay must answer instead."""
        self._seed_row(layered)

        result = layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_MODE": "block"}, "scheduler", skip_service_management=True)

        assert isinstance(result, set), result
        assert ("ALPHA_MODE", 0) not in _global_rows(layered)
        assert layered.get_config()["ALPHA_MODE"] == "block"  # from the template, not from a row

    def test_editing_down_to_the_plugin_default_keeps_the_row(self, layered):
        """The mirror, and the update-path twin of facet 1: "off" is the PLUGIN default but not
        the template's, so it is a real override and the row must survive the edit."""
        self._seed_row(layered)

        result = layered.save_config({"USE_TEMPLATE": "low high", "ALPHA_MODE": "off"}, "scheduler", skip_service_management=True)

        assert isinstance(result, set), result
        assert _global_rows(layered)[("ALPHA_MODE", 0)] == ("off", "scheduler")
        assert layered.get_config()["ALPHA_MODE"] == "off"
