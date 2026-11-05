"""Template CRUD validation and the custom config upsert/read paths.

Each refusal asserts the message a caller shows and that no template row was written or changed.
"""

import pytest
from sqlalchemy import func, select

from fixtures.seed import add_global_value, add_service_setting, add_custom_config_row, seed_minimal, session
from model import Custom_configs, Template_custom_configs, Template_settings, Template_steps, Templates

pytestmark = pytest.mark.multiengine

READONLY = "The database is read-only, the changes will not be saved"


def _count(db, model, **filters):
    with session(db) as s:
        return s.scalar(select(func.count()).select_from(model).filter_by(**filters))


@pytest.fixture
def seeded(db):
    seed_minimal(db)
    assert db.checked_changes(["custom_configs"], value=False) == ""
    return db


def _template(**overrides):
    base = {
        "plugin_id": None,
        "name": "Proxy template",
        "settings": {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_URL_1": "/api"},
        "steps": [
            {"title": "Proxy", "subtitle": "Where to", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"], "configs": ["server-http/route.conf"]},
            {"title": "Extra", "settings": [], "configs": []},
        ],
        "configs": [{"type": "server-http", "name": "route", "data": "set $x 1;\n"}],
    }
    return base | overrides


class TestCreateTemplate:
    def test_a_valid_payload_is_stored_with_ordered_steps_settings_and_configs(self, seeded):
        assert seeded.create_template("proxy", **_template()) == ""
        details = seeded.get_template_details("proxy")
        assert (details["name"], details["method"], details["plugin_id"]) == ("Proxy template", "ui", None)
        assert [(s["title"], s["subtitle"]) for s in details["steps"]] == [("Proxy", "Where to"), ("Extra", "")]
        assert [(s["key"], s["default"], s["step_id"]) for s in details["settings"]] == [("USE_REVERSE_PROXY", "yes", 1), ("REVERSE_PROXY_URL_1", "/api", 1)]
        assert [(c["key"], c["data"], c["step_id"]) for c in details["configs"]] == [("server_http/route.conf", "set $x 1;\n", 1)]

    def test_a_template_can_be_attached_to_a_plugin_and_the_method_defaults_to_ui(self, seeded):
        assert seeded.create_template("proxy", **_template(plugin_id=" general "), method="") == ""
        details = seeded.get_template_details("proxy")
        assert (details["plugin_id"], details["method"]) == ("general", "ui")

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"name": "   "}, "Template name cannot be empty"),
            ({"plugin_id": "ghost"}, "Plugin ghost does not exist"),
            ({"steps": []}, "A template must contain at least one step"),
            ({"settings": {" ": "x"}}, "Template settings keys must be non-empty strings"),
            ({"steps": [{"title": " ", "settings": [], "configs": []}]}, "Step 1 must have a title"),
            ({"steps": [{"title": "t", "settings": "USE_REVERSE_PROXY", "configs": []}]}, "Step 1 settings must be a list"),
            ({"steps": [{"title": "t", "settings": [3], "configs": []}]}, "Step 1 contains an invalid setting reference"),
            ({"steps": [{"title": "t", "settings": ["MISSING"], "configs": []}]}, "Step 1 references unknown setting MISSING"),
            ({"steps": [{"title": "t", "settings": [], "configs": "x"}]}, "Step 1 configs must be a list"),
            ({"steps": [{"title": "t", "settings": [], "configs": [5]}]}, "Step 1 contains an invalid config reference"),
            ({"steps": [{"title": "t", "settings": [], "configs": ["nonsense"]}]}, "Step 1 contains an invalid config reference"),
            ({"steps": [{"title": "t", "settings": [], "configs": ["http/x.conf"]}]}, "Step 1 contains an invalid config reference"),
            ({"steps": [{"title": "t", "settings": [], "configs": ["server-http/"]}]}, "Step 1 contains an invalid config reference"),
            (
                {"settings": {"USE_TEMPLATE": "x"}, "steps": [{"title": "t", "settings": ["USE_TEMPLATE"], "configs": []}], "configs": []},
                "Setting USE_TEMPLATE cannot be part of a template",
            ),
            (
                {"settings": {"NOT_A_SETTING": "x"}, "steps": [{"title": "t", "settings": ["NOT_A_SETTING"], "configs": []}], "configs": []},
                "Unknown settings: NOT_A_SETTING",
            ),
            ({"configs": ["not-a-dict"]}, "Config entries must be objects"),
            ({"configs": [{"type": "http", "name": "route"}]}, "Invalid config definition at index 1"),
            ({"configs": []}, "Step references unknown config server_http/route.conf"),
            (
                {"configs": [{"type": "server-http", "name": "route"}, {"type": "server_http", "name": "route.conf"}]},
                "Duplicate config server_http/route.conf",
            ),
            (
                {"configs": [{"type": "server-http", "name": "route"}, {"type": "server-http", "name": "other"}]},
                "Config server_http/other.conf is not assigned to any step",
            ),
        ],
    )
    def test_invalid_payloads_are_refused_and_nothing_is_written(self, seeded, kwargs, message):
        assert seeded.create_template("proxy", **_template(**kwargs)) == message
        assert _count(seeded, Templates) == 0 and _count(seeded, Template_steps) == 0

    def test_a_setting_listed_in_two_steps_and_an_unassigned_setting_are_refused(self, seeded):
        twice = _template(
            steps=[
                {"title": "a", "settings": ["USE_REVERSE_PROXY"], "configs": ["server-http/route.conf"]},
                {"title": "b", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"], "configs": []},
            ]
        )
        assert seeded.create_template("proxy", **twice) == "Setting USE_REVERSE_PROXY is assigned to multiple steps"
        unassigned = _template(steps=[{"title": "a", "settings": ["USE_REVERSE_PROXY"], "configs": ["server-http/route.conf"]}])
        assert seeded.create_template("proxy", **unassigned) == "Settings REVERSE_PROXY_URL_1 are not assigned to any step"
        two_configs = _template(
            steps=[
                {"title": "a", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"], "configs": ["server-http/route.conf"]},
                {"title": "b", "settings": [], "configs": ["server-http/route.conf"]},
            ]
        )
        assert seeded.create_template("proxy", **two_configs) == "Config server_http/route.conf is assigned to multiple steps"
        assert _count(seeded, Templates) == 0

    def test_duplicates_of_the_id_and_the_name_are_refused(self, seeded):
        assert seeded.create_template("proxy", **_template()) == ""
        assert seeded.create_template(" ", **_template(name="Other")) == "Template id is required"
        assert seeded.create_template("proxy", **_template(name="Other")) == "Template proxy already exists"
        assert seeded.create_template("other", **_template()) == "Template name Proxy template already exists"
        assert _count(seeded, Templates) == 1

    def test_the_config_order_follows_an_explicit_order_before_the_list_position(self, seeded):
        payload = _template(
            steps=[{"title": "a", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"], "configs": ["server-http/first.conf", "modsec/second.conf"]}],
            configs=[
                {"type": "server-http", "name": "first", "data": "a", "order": 5},
                {"type": "modsec", "name": "second", "data": b"b".decode(), "order": 1},
            ],
        )
        assert seeded.create_template("proxy", **payload) == ""
        assert [c["key"] for c in seeded.get_template_details("proxy")["configs"]] == ["modsec/second.conf", "server_http/first.conf"]

    def test_read_only_mode_refuses(self, seeded):
        seeded.readonly = True
        assert seeded.create_template("proxy", **_template()) == READONLY
        assert _count(seeded, Templates) == 0


class TestUpdateTemplate:
    @pytest.fixture
    def stored(self, seeded):
        assert seeded.create_template("proxy", **_template()) == ""
        assert seeded.checked_changes(["custom_configs"], value=False) == ""
        return seeded

    def test_an_update_without_fields_keeps_the_content_and_marks_the_template_as_ui_owned(self, stored):
        with session(stored) as s:
            s.query(Templates).filter_by(id="proxy").update({"method": "manual"})
        assert stored.update_template("proxy") == ""
        details = stored.get_template_details("proxy")
        assert details["method"] == "ui" and len(details["steps"]) == 2 and len(details["configs"]) == 1
        assert [s["key"] for s in details["settings"]] == ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"]
        meta = stored.get_metadata()
        assert meta["custom_configs_changed"] is True
        assert list(meta["plugins_config_changed"]) == ["general"]

    def test_name_plugin_settings_steps_and_configs_are_replaced(self, stored):
        assert (
            stored.update_template(
                "proxy",
                plugin_id="general",
                name="Renamed",
                settings={"SECURITY_MODE": "detect"},
                steps=[{"title": "Only", "settings": ["SECURITY_MODE"], "configs": ["modsec/m.conf"]}],
                configs=[{"type": "modsec", "name": "m", "data": "SecRuleEngine On"}],
            )
            == ""
        )
        details = stored.get_template_details("proxy")
        assert (details["name"], details["plugin_id"]) == ("Renamed", "general")
        assert [s["key"] for s in details["settings"]] == ["SECURITY_MODE"] and [c["key"] for c in details["configs"]] == ["modsec/m.conf"]
        assert _count(stored, Template_steps, template_id="proxy") == 1

    def test_the_plugin_can_be_detached(self, stored):
        assert stored.update_template("proxy", plugin_id="general") == ""
        assert stored.update_template("proxy", plugin_id=" ") == ""
        assert stored.get_template_details("proxy")["plugin_id"] is None

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"plugin_id": "ghost"}, "Plugin ghost does not exist"),
            ({"name": " "}, "Template name cannot be empty"),
            ({"name": "Taken"}, "Template name Taken already exists"),
            ({"steps": []}, "A template must contain at least one step"),
            ({"steps": [{"title": "", "settings": [], "configs": []}]}, "Step 1 must have a title"),
        ],
    )
    def test_refusals_leave_the_stored_template_unchanged(self, stored, kwargs, message):
        assert stored.create_template("taken", **_template(name="Taken", configs=[{"type": "server-http", "name": "route", "data": "x"}])) == ""
        before = stored.get_template_details("proxy")
        assert stored.update_template("proxy", **kwargs) == message
        after = stored.get_template_details("proxy")
        assert {k: v for k, v in after.items() if k != "last_update"} == {k: v for k, v in before.items() if k != "last_update"}

    def test_the_same_name_may_be_kept_and_a_missing_template_is_reported(self, stored):
        assert stored.update_template("proxy", name="Proxy template") == ""
        assert stored.update_template("ghost") == "Template not found"

    def test_read_only_mode_refuses(self, stored):
        stored.readonly = True
        assert stored.update_template("proxy", name="X") == READONLY
        assert stored.get_template_details("proxy")["name"] == "Proxy template"


class TestDeleteTemplate:
    @pytest.fixture
    def stored(self, seeded):
        assert seeded.create_template("proxy", **_template()) == ""
        assert seeded.checked_changes(["custom_configs"], value=False) == ""
        return seeded

    def test_an_unused_template_is_deleted_with_its_children_and_flags_the_change(self, stored):
        assert stored.delete_template("proxy") == ""
        assert _count(stored, Templates) == 0
        for model in (Template_steps, Template_settings, Template_custom_configs):
            assert _count(stored, model) == 0
        assert stored.get_metadata()["custom_configs_changed"] is True

    def test_a_template_used_globally_is_refused_and_kept(self, stored):
        add_global_value(stored, setting_id="USE_TEMPLATE", value="proxy", method="ui")
        assert stored.delete_template("proxy") == "Template is currently used by the global settings"
        assert _count(stored, Templates) == 1 and _count(stored, Template_steps) == 2

    def test_a_template_used_by_a_service_is_refused_and_kept(self, stored):
        add_service_setting(stored, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="proxy", method="ui")
        assert stored.delete_template("proxy") == "Template is currently used by a service"
        assert _count(stored, Templates) == 1

    def test_the_reference_check_looks_at_this_template_only(self, stored):
        add_service_setting(stored, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="other", method="ui")
        assert stored.delete_template("proxy") == ""

    def test_missing_and_read_only(self, stored):
        assert stored.delete_template("ghost") == "Template not found"
        stored.readonly = True
        assert stored.delete_template("proxy") == READONLY
        assert _count(stored, Templates) == 1


class TestTemplateReferenceNormalisation:
    @pytest.mark.parametrize(
        "reference, expected",
        [
            ("", None),
            ("   ", None),
            ("nosep", None),
            ("http/x.conf", None),
            ("server-http/   ", None),
            ("server-http/.conf", None),
            ("Server-HTTP/x", "server_http/x.conf"),
            (" modsec-crs / name.conf ", "modsec_crs/name.conf"),
            ("crs_plugins_before/a.b.conf", "crs_plugins_before/a.b.conf"),
        ],
    )
    def test_references_are_canonicalised_or_rejected(self, seeded, reference, expected):
        assert seeded._normalize_template_config_reference(reference) == expected


class TestUpsertCustomConfig:
    CONFIG = {"service_id": None, "type": "http", "name": "snippet", "data": "# one", "method": "ui"}

    def test_insert_then_update_in_place_and_flag(self, seeded):
        assert seeded.upsert_custom_config("http", "snippet", dict(self.CONFIG)) == ""
        row = seeded.get_custom_config("http", "snippet")
        assert (row["data"], row["method"], row["is_draft"]) == (b"# one", "ui", False)
        assert seeded.get_metadata()["custom_configs_changed"] is True
        assert seeded.upsert_custom_config("http", "snippet", self.CONFIG | {"data": b"# two", "is_draft": True, "method": "api"}) == ""
        row = seeded.get_custom_config("http", "snippet")
        assert (row["data"], row["method"], row["is_draft"]) == (b"# two", "api", True)
        assert _count(seeded, Custom_configs) == 1

    def test_the_checksum_is_computed_unless_given(self, seeded):
        from common_utils import bytes_hash  # type: ignore

        assert seeded.upsert_custom_config("http", "snippet", dict(self.CONFIG)) == ""
        assert seeded.get_custom_config("http", "snippet")["checksum"] == bytes_hash(b"# one", algorithm="sha256")
        assert seeded.upsert_custom_config("http", "snippet", self.CONFIG | {"checksum": "given"}) == ""
        assert seeded.get_custom_config("http", "snippet")["checksum"] == "given"

    def test_new_refuses_an_existing_config_and_keeps_its_content(self, seeded):
        assert seeded.upsert_custom_config("http", "snippet", dict(self.CONFIG)) == ""
        assert seeded.upsert_custom_config("http", "snippet", self.CONFIG | {"data": "# other"}, new=True) == "The custom config already exists"
        assert seeded.get_custom_config("http", "snippet")["data"] == b"# one"

    def test_a_service_scoped_config_is_a_separate_row(self, seeded):
        assert (
            seeded.upsert_custom_config(
                "server_http", "snippet", self.CONFIG | {"type": "server_http", "service_id": "app1.example.com"}, service_id="app1.example.com"
            )
            == ""
        )
        assert seeded.upsert_custom_config("server_http", "snippet", self.CONFIG | {"type": "server_http"}) == ""
        assert _count(seeded, Custom_configs, name="snippet") == 2

    def test_read_only_mode_refuses(self, seeded):
        seeded.readonly = True
        assert seeded.upsert_custom_config("http", "snippet", dict(self.CONFIG)) == READONLY
        assert _count(seeded, Custom_configs) == 0


class TestGetCustomConfigsWithTemplates:
    def _use(self, db, template_id="proxy", service="app1.example.com"):
        add_global_value(db, setting_id="MULTISITE", value="yes", method="ui")
        add_service_setting(db, service_id=service, setting_id="USE_TEMPLATE", value=template_id, method="ui")

    def test_a_service_inherits_the_configs_of_its_template(self, seeded):
        assert seeded.create_template("proxy", **_template()) == ""
        self._use(seeded)
        configs = seeded.get_custom_configs(as_dict=True)
        key = "app1.example.com_server-http_route"  # the template reference keeps the hyphenated type
        assert configs[key]["method"] == "default" and configs[key]["template"] == "proxy" and configs[key]["data"] == b"set $x 1;\n"
        assert [c["name"] for c in seeded.get_custom_configs(with_data=False)] == ["route"]
        assert "data" not in seeded.get_custom_configs(with_data=False)[0]

    def test_an_own_config_with_the_same_type_and_name_suppresses_the_template_one(self, seeded):
        assert seeded.create_template("proxy", **_template()) == ""
        self._use(seeded)
        add_custom_config_row(seeded, service_id="app1.example.com", type="server_http", name="route", data=b"# mine", method="ui")
        configs = seeded.get_custom_configs()
        assert len(configs) == 1 and configs[0]["data"] == b"# mine" and configs[0]["template"] is None

    def test_drafts_are_hidden_unless_asked_for(self, seeded):
        from fixtures.seed import add_service

        add_service(seeded, "draft.example.com", is_draft=True)
        add_custom_config_row(seeded, service_id="draft.example.com", type="server_http", name="d", data=b"# d", method="ui")
        add_custom_config_row(seeded, service_id=None, type="http", name="g", data=b"# g", method="ui")
        assert [c["name"] for c in seeded.get_custom_configs()] == ["g"]
        assert sorted(c["name"] for c in seeded.get_custom_configs(with_drafts=True)) == ["d", "g"]

    def test_the_plain_listing_and_the_dict_listing_agree_without_any_template(self, seeded):
        add_custom_config_row(seeded, service_id="app1.example.com", type="server_http", name="a", data=b"# a", method="ui")
        add_custom_config_row(seeded, service_id=None, type="http", name="g", data=b"# g", method="ui")
        assert set(seeded.get_custom_configs(as_dict=True)) == {"app1.example.com_server_http_a", "http_g"}


def test_the_global_crs_incompatibility_applies_to_service_scoped_modsec_crs_only(seeded):
    assert seeded.get_custom_config_compatibility_error("modsec-crs", service_id="app1.example.com") == ""
    from fixtures.seed import add_setting

    add_setting(seeded, "USE_MODSECURITY_GLOBAL_CRS", context="global", type="check", regex="^(yes|no)$", default="no")
    add_global_value(seeded, setting_id="USE_MODSECURITY_GLOBAL_CRS", value="yes", method="ui")
    message = seeded.get_custom_config_compatibility_error("modsec-crs", service_id="app1.example.com")
    assert message == seeded.GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR
    assert seeded.get_custom_config_compatibility_error("modsec-crs", service_id="global") == ""
    assert seeded.get_custom_config_compatibility_error("modsec-crs") == ""
    assert seeded.get_custom_config_compatibility_error("server-http", service_id="app1.example.com") == ""
