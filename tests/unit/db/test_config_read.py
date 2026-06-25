"""DatabaseConfigReadMixin — setting validation and the multisite config assembly.

The multisite brain: prefixing, suffix expansion, per-service override precedence and
the global -> per-service default propagation. Uses ``seed_multisite``.
"""

import pytest

from fixtures.seed import add_setting, seed_minimal, seed_multisite


class TestIsValidSetting:
    def test_valid_global(self, db):
        seed_minimal(db)
        assert db.is_valid_setting("MULTISITE", value="yes") == (True, "")

    def test_regex_mismatch(self, db):
        seed_minimal(db)
        ok, msg = db.is_valid_setting("MULTISITE", value="maybe")
        assert ok is False
        assert "not matching regex" in msg

    def test_check_accepts_truthy_aliases(self, db):
        seed_minimal(db)
        for v in ("true", "True", "on", "1", "y", "enabled"):
            assert db.is_valid_setting("MULTISITE", value=v) == (True, ""), v

    def test_check_accepts_falsy_aliases(self, db):
        seed_minimal(db)
        for v in ("false", "off", "0", "n", "disabled", "OFF"):
            assert db.is_valid_setting("MULTISITE", value=v) == (True, ""), v

    def test_check_still_rejects_non_boolean(self, db):
        seed_minimal(db)
        ok, msg = db.is_valid_setting("MULTISITE", value="maybe")
        assert ok is False and "not matching regex" in msg

    def test_non_check_setting_value_not_coerced(self, db):
        seed_minimal(db)
        # SECURITY_MODE is text (^.*$): a boolean-looking value must validate as plain text.
        assert db.is_valid_setting("SECURITY_MODE", value="on") == (True, "")

    def test_check_prefixed_alias_via_extra_services(self, db):
        seed_minimal(db)
        # USE_REVERSE_PROXY is a multisite check; a prefixed alias resolves + normalizes.
        assert db.is_valid_setting("app1.example.com_USE_REVERSE_PROXY", value="on", extra_services=["app1.example.com"]) == (True, "")

    def test_check_prefixed_falsy_alias_via_db_service(self, db):
        seed_minimal(db)  # seeds service app1.example.com -> resolved via the DB services scan
        assert db.is_valid_setting("app1.example.com_USE_REVERSE_PROXY", value="disabled") == (True, "")

    def test_missing(self, db):
        seed_minimal(db)
        assert db.is_valid_setting("DOES_NOT_EXIST") == (False, "missing")

    def test_not_multisite(self, db):
        seed_minimal(db)
        # MULTISITE is a global setting; requesting multisite validation rejects it.
        assert db.is_valid_setting("MULTISITE", multisite=True) == (False, "not multisite")

    def test_not_multiple(self, db):
        seed_minimal(db)
        # MULTISITE is not a 'multiple' setting; a suffixed key is rejected.
        assert db.is_valid_setting("MULTISITE_1") == (False, "not multiple")

    def test_multiple_ok(self, db):
        seed_minimal(db)
        assert db.is_valid_setting("REVERSE_PROXY_URL_1", value="http://x") == (True, "")

    def test_invalid_stored_regex(self, db):
        seed_minimal(db)
        add_setting(db, "BAD_REGEX", regex="[")  # unbalanced bracket -> re.error
        ok, msg = db.is_valid_setting("BAD_REGEX", value="anything")
        assert ok is False
        assert "invalid regex" in msg

    def test_ignore_regex_check_bypass(self, db):
        seed_minimal(db)
        db._ignore_regex_check = True
        assert db.is_valid_setting("MULTISITE", value="totally-invalid") == (True, "")

    def test_size_accepts_aliases(self, db):
        seed_minimal(db)
        add_setting(db, "MEM_SIZE", type="size", regex=r"^\d+([kKmMgG])?$", default="0")
        for v in ("64m", "64M", "64 m", "1mb", "131072", "0"):
            assert db.is_valid_setting("MEM_SIZE", value=v) == (True, ""), v

    def test_size_rejects_fraction(self, db):
        seed_minimal(db)
        add_setting(db, "MEM_SIZE", type="size", regex=r"^\d+([kKmMgG])?$", default="0")
        ok, _ = db.is_valid_setting("MEM_SIZE", value="1.5g")
        assert ok is False

    def test_duration_accepts_aliases_and_compound(self, db):
        seed_minimal(db)
        add_setting(db, "MY_TIMEOUT", type="duration", regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", default="0")
        for v in ("30s", "30sec", "5min", "6month", "1h30m", "1d12h", "60", "500ms"):
            assert db.is_valid_setting("MY_TIMEOUT", value=v) == (True, ""), v

    def test_duration_rejects_garbage(self, db):
        seed_minimal(db)
        add_setting(db, "MY_TIMEOUT", type="duration", regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", default="0")
        ok, _ = db.is_valid_setting("MY_TIMEOUT", value="30x")
        assert ok is False

    @pytest.mark.parametrize("bad", ["30m1h", "1h1h", "1h1d"])
    def test_duration_rejects_order_invalid_compound(self, db, bad):
        # The permissive regex matches these, but NGINX rejects order-invalid units.
        # is_valid_setting must reject via the authoritative parser.
        seed_minimal(db)
        add_setting(db, "MY_TIMEOUT", type="duration", regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", default="0")
        ok, _ = db.is_valid_setting("MY_TIMEOUT", value=bad)
        assert ok is False

    def test_service_prefix_via_extra_services(self, db):
        seed_minimal(db)
        assert db.is_valid_setting("app1.example.com_USE_REVERSE_PROXY", value="yes", extra_services=["app1.example.com"]) == (True, "")

    def test_service_prefixed_global_setting_rejected(self, db):
        seed_minimal(db)
        # A global setting addressed with a known service prefix resolves via the DB
        # services scan, which flips multisite=True -> 'not multisite'.
        assert db.is_valid_setting("app1.example.com_MULTISITE") == (False, "not multisite")


class TestGetConfig:
    def test_global_override_and_server_name(self, db):
        seed_multisite(db)
        cfg = db.get_config(methods=False)
        assert cfg["MULTISITE"] == "yes"
        assert set(cfg["SERVER_NAME"].split()) == {"app1.example.com", "app2.example.com"}

    def test_multisite_prefixing_and_override_precedence(self, db):
        seed_multisite(db)
        cfg = db.get_config(methods=False)
        assert cfg["app1.example.com_USE_REVERSE_PROXY"] == "yes"  # per-service override
        assert cfg["app1.example.com_SECURITY_MODE"] == "block"  # override beats the global default
        assert cfg["app2.example.com_SECURITY_MODE"] == "detect"  # global multisite default propagates

    def test_suffix_expansion(self, db):
        seed_multisite(db)
        cfg = db.get_config(methods=False)
        assert cfg["app1.example.com_REVERSE_PROXY_URL_1"] == "http://backend1"

    def test_methods_true_returns_metadata(self, db):
        seed_multisite(db)
        cfg = db.get_config(methods=True)
        assert cfg["MULTISITE"]["value"] == "yes"
        assert cfg["MULTISITE"]["method"] == "scheduler"

    def test_service_filter_strips_prefix(self, db):
        seed_multisite(db)
        cfg = db.get_config(methods=False, service="app1.example.com")
        assert cfg["USE_REVERSE_PROXY"] == "yes"
        assert cfg["SECURITY_MODE"] == "block"


class TestGetServicesSettings:
    def test_returns_one_dict_per_service(self, db):
        seed_multisite(db)
        services = db.get_services_settings(methods=False)
        assert len(services) == 2  # app1 + app2
        assert all("MULTISITE" in svc for svc in services)  # global keys retained, unprefixed
        assert any(svc.get("USE_REVERSE_PROXY") == "yes" for svc in services)  # app1's override


class TestGetConfigTemplateExpansion:
    """get_config expands USE_TEMPLATE into per-setting defaults, tagging them template=<id>,
    without overriding values that were set explicitly."""

    def _make_template(self, db, *, default="tmpl-default"):
        return db.create_template(
            "low",
            name="Low",
            settings={"USE_REVERSE_PROXY": default},
            steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}],
        )

    def test_global_template_applies_defaults(self, db):
        from fixtures.seed import add_global_value

        seed_minimal(db)
        assert self._make_template(db, default="yes") == ""
        add_global_value(db, setting_id="USE_TEMPLATE", value="low")
        cfg = db.get_config(methods=True)
        assert cfg["USE_REVERSE_PROXY"]["value"] == "yes"
        assert cfg["USE_REVERSE_PROXY"]["template"] == "low"

    def test_service_template_applies_defaults(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._make_template(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="low")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "tmpl-default"
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["template"] == "low"

    def test_explicit_service_value_beats_template(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)  # app1 explicitly sets USE_REVERSE_PROXY=yes (method manual)
        self._make_template(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="low")
        cfg = db.get_config(methods=True)
        assert cfg["app1.example.com_USE_REVERSE_PROXY"]["value"] == "yes"  # explicit override survives
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "tmpl-default"  # template fills the gap
