"""DatabaseConfigReadMixin — setting validation and the multisite config assembly.

The multisite brain: prefixing, suffix expansion, per-service override precedence and
the global -> per-service default propagation. Uses ``seed_multisite``.
"""

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
