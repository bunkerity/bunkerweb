"""DatabaseCustomConfigsMixin — global/per-service NGINX config snippets."""

import pytest

from fixtures.seed import seed_minimal


@pytest.fixture
def cdb(db):
    seed_minimal(db)
    return db


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
