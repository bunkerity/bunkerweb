"""DatabaseCustomConfigsMixin — global/per-service NGINX config snippets."""

import pytest

from fixtures.seed import add_service_setting, seed_minimal, seed_multisite


@pytest.fixture
def cdb(db):
    seed_minimal(db)
    return db


def _template_with_server_http_config(db, template_id="low", *, name="Low", cfg_name="tmplcfg", data="# from-template"):
    """Create a template carrying one server_http custom config (http is NOT a valid
    template config type — only the server-scoped MULTISITE_CUSTOM_CONFIG_TYPES are)."""
    return db.create_template(
        template_id,
        name=name,
        settings={"USE_REVERSE_PROXY": "yes"},
        steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"], "configs": [f"server_http/{cfg_name}.conf"]}],
        configs=[{"type": "server_http", "name": cfg_name, "data": data}],
    )


class TestSaveCustomConfigs:
    def test_save_and_read_back(self, cdb):
        assert cdb.save_custom_configs([{"type": "http", "name": "snippet", "data": "# hello", "method": "manual"}], "manual") == ""
        cfg = cdb.get_custom_config("http", "snippet")
        assert cfg["data"] == b"# hello"
        assert cfg["method"] == "manual"
        assert cfg["is_draft"] is False

    def test_get_custom_configs_list_and_as_dict(self, cdb):
        cdb.save_custom_configs([{"type": "http", "name": "snippet", "data": "# hi", "method": "manual"}], "manual")
        listed = cdb.get_custom_configs()
        assert len(listed) == 1
        assert listed[0]["type"] == "http" and listed[0]["name"] == "snippet"
        as_dict = cdb.get_custom_configs(as_dict=True)
        assert "http_snippet" in as_dict

    def test_type_normalization(self, cdb):
        # hyphenated/upper type is normalized to the underscore enum form.
        assert cdb.save_custom_configs([{"type": "Server-Http", "name": "n", "data": "# x", "method": "manual"}], "manual") == ""
        assert cdb.get_custom_config("server_http", "n")["data"] == b"# x"

    def test_empty_ui_payload_is_data_loss_guarded(self, cdb):
        cdb.save_custom_configs([{"type": "http", "name": "x", "data": "# a", "method": "ui"}], "ui")
        # An empty ui payload must NOT wipe existing ui-owned rows.
        assert cdb.save_custom_configs([], "ui") == ""
        assert len(cdb.get_custom_configs()) == 1


class TestUpsertCustomConfig:
    def test_insert_then_update(self, cdb):
        base = {"type": "http", "name": "c", "data": "# v1", "method": "manual"}
        assert cdb.upsert_custom_config("http", "c", base) == ""
        assert cdb.get_custom_config("http", "c")["data"] == b"# v1"
        # update path replaces data
        assert cdb.upsert_custom_config("http", "c", {**base, "data": "# v2"}) == ""
        assert cdb.get_custom_config("http", "c")["data"] == b"# v2"

    def test_new_flag_rejects_existing(self, cdb):
        base = {"type": "http", "name": "c", "data": "# v1", "method": "manual"}
        cdb.upsert_custom_config("http", "c", base)
        assert cdb.upsert_custom_config("http", "c", base, new=True) == "The custom config already exists"


class TestGetCustomConfig:
    def test_missing_returns_empty_dict(self, cdb):
        assert cdb.get_custom_config("http", "nope") == {}


class TestCompatibilityError:
    def test_non_modsec_crs_ok(self, cdb):
        assert cdb.get_custom_config_compatibility_error("http", service_id="app1.example.com") == ""

    def test_global_scope_ok(self, cdb):
        assert cdb.get_custom_config_compatibility_error("modsec_crs", service_id="global") == ""

    def test_modsec_crs_ok_when_global_crs_off(self, cdb):
        # no USE_MODSECURITY_GLOBAL_CRS configured -> treated as off -> no error
        assert cdb.get_custom_config_compatibility_error("modsec_crs", service_id="app1.example.com") == ""

    def test_modsec_crs_blocked_when_global_crs_on(self, cdb):
        from fixtures.seed import add_global_value, add_setting

        add_setting(cdb, "USE_MODSECURITY_GLOBAL_CRS", context="global", regex="^(yes|no)$", default="no")
        add_global_value(cdb, setting_id="USE_MODSECURITY_GLOBAL_CRS", value="yes")
        assert cdb.get_custom_config_compatibility_error("modsec_crs", service_id="app1.example.com") != ""


class TestSaveExplodedPayload:
    """The UI/API submit configs in an 'exploded' shape: {"value": data, "exploded": (service_id, type, name)}."""

    def test_exploded_global(self, cdb):
        # exploded[0] falsy -> global config, no service_id.
        assert cdb.save_custom_configs([{"value": "# g", "exploded": ("", "http", "glob")}], "ui") == ""
        cfg = cdb.get_custom_config("http", "glob")
        assert cfg["data"] == b"# g"
        assert cfg["service_id"] is None
        assert cfg["method"] == "ui"

    def test_exploded_service(self, cdb):
        # exploded[0] truthy and the service exists -> per-service config.
        assert cdb.save_custom_configs([{"value": "# s", "exploded": ("app1.example.com", "server-http", "svc")}], "ui") == ""
        cfg = cdb.get_custom_config("server_http", "svc", service_id="app1.example.com")
        assert cfg["data"] == b"# s"
        assert cfg["service_id"] == "app1.example.com"

    def test_exploded_unknown_service_reports_message(self, cdb):
        # exploded[0] points at a missing service -> the not-found message is reported
        # (the row insert also fails the FK on PG/MariaDB, which appends the integrity error).
        msg = cdb.save_custom_configs([{"value": "# s", "exploded": ("ghost.example.com", "http", "n")}], "ui")
        assert "Service ghost.example.com not found" in msg


class TestSaveCustomConfigsCrossMethodUpdate:
    """save_custom_configs deletes only rows owned by the incoming method, then reconciles
    surviving rows owned by OTHER methods through the compatibility rules."""

    def test_manual_save_updates_surviving_ui_row(self, cdb):
        cdb.save_custom_configs([{"type": "http", "name": "u", "data": "# ui", "method": "ui"}], "ui")
        # manual save deletes manual-owned rows only; the ui row survives and is updated in place.
        assert cdb.save_custom_configs([{"type": "http", "name": "u", "data": "# manual", "method": "manual"}], "manual") == ""
        assert cdb.get_custom_config("http", "u")["data"] == b"# manual"

    def test_scheduler_save_overwrites_ui_row_method(self, cdb):
        cdb.save_custom_configs([{"type": "http", "name": "u", "data": "# ui", "method": "ui"}], "ui")
        # scheduler is compatible-over ui -> data updated AND method reassigned to scheduler.
        assert cdb.save_custom_configs([{"type": "http", "name": "u", "data": "# sched", "method": "scheduler"}], "scheduler") == ""
        cfg = cdb.get_custom_config("http", "u")
        assert cfg["data"] == b"# sched"
        assert cfg["method"] == "scheduler"


class TestAutoconfDisableCleanup:
    def test_orphan_autoconf_config_marked_draft(self, cdb):
        cdb.save_custom_configs([{"type": "http", "name": "keep", "data": "# k", "method": "autoconf"}], "autoconf")
        # disable_cleanup: the orchestrator re-emits only "other"; the no-longer-emitted "keep"
        # is NOT deleted but flipped to draft so it follows its service.
        assert cdb.save_custom_configs([{"type": "http", "name": "other", "data": "# o", "method": "autoconf"}], "autoconf", disable_cleanup=True) == ""
        kept = cdb.get_custom_config("http", "keep")
        assert kept  # survived the cleanup-disabled save
        assert kept["is_draft"] is True
        assert cdb.get_custom_config("http", "other")["is_draft"] is False


class TestGetCustomConfigsTemplateMerge:
    """A service with USE_TEMPLATE inherits the template's custom configs (method='default',
    template=<id>) unless a real row of the same type/name overrides it."""

    def test_template_config_surfaces_for_service(self, db):
        seed_multisite(db)
        assert _template_with_server_http_config(db) == ""
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        tmpl = [c for c in db.get_custom_configs() if c.get("template") == "low"]
        assert len(tmpl) == 1
        assert tmpl[0]["service_id"] == "app1.example.com"
        assert tmpl[0]["name"] == "tmplcfg"
        assert tmpl[0]["type"] == "server-http"  # synthesized back to hyphenated form
        assert tmpl[0]["method"] == "default"
        assert tmpl[0]["data"] == b"# from-template"

    def test_template_merge_as_dict(self, db):
        seed_multisite(db)
        _template_with_server_http_config(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        cfgs = db.get_custom_configs(as_dict=True)
        assert "app1.example.com_server-http_tmplcfg" in cfgs
        assert cfgs["app1.example.com_server-http_tmplcfg"]["template"] == "low"

    def test_real_row_suppresses_template_config(self, db):
        seed_multisite(db)
        _template_with_server_http_config(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        # a real per-service row for the same type/name suppresses the template-provided one.
        db.save_custom_configs(
            [{"service_id": "app1.example.com", "type": "server_http", "name": "tmplcfg", "data": "# real", "method": "manual"}],
            "manual",
        )
        matching = [c for c in db.get_custom_configs() if c["name"] == "tmplcfg" and c["service_id"] == "app1.example.com"]
        assert len(matching) == 1
        assert matching[0]["template"] is None  # the real row wins
        assert matching[0]["data"] == b"# real"


class TestGetCustomConfigTemplateFallback:
    """get_custom_config (single) falls back to the service's template when no real row exists."""

    def test_single_config_from_template(self, db):
        seed_multisite(db)
        _template_with_server_http_config(db, cfg_name="only", data="# tonly")
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        cfg = db.get_custom_config("server_http", "only", service_id="app1.example.com")
        assert cfg["template"] == "low"
        assert cfg["method"] == "default"
        assert cfg["data"] == b"# tonly"

    def test_single_config_no_match_returns_empty(self, db):
        seed_multisite(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        # USE_TEMPLATE set, but no such template/config row -> {}
        assert db.get_custom_config("server_http", "missing", service_id="app1.example.com") == {}
