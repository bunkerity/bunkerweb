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

    def _make_template(self, db, *, default="yes"):
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
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "yes"
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["template"] == "low"

    def test_explicit_service_value_beats_template(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)  # app1 explicitly sets USE_REVERSE_PROXY=yes (method manual)
        self._make_template(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low")
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="low")
        cfg = db.get_config(methods=True)
        assert cfg["app1.example.com_USE_REVERSE_PROXY"]["value"] == "yes"  # explicit override survives
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "yes"  # template fills the gap


class TestGetConfigMultiTemplateExpansion:
    """USE_TEMPLATE is an ORDERED LIST: layers apply left to right, last-wins.

    The precedence is not an added branch -- it falls out of the existing skip-guards, which
    only stop a layer on a NON-default method. These tests pin that, and pin the two things a
    naive port gets wrong: per-service order (two services can share layers in different
    orders) and the ``template`` provenance field (the owning LAYER, never the whole list)."""

    @staticmethod
    def _layers(db):
        # base sets both keys; hardening overrides only one of them.
        assert (
            db.create_template(
                "base",
                name="Base",
                # NOT "detect": seed_multisite sets the GLOBAL SECURITY_MODE to "detect", so a
                # layer using it too would make "base won" and "the global propagated"
                # indistinguishable -- every assertion below would pass with the overlay removed.
                settings={"USE_REVERSE_PROXY": "yes", "SECURITY_MODE": "audit"},
                steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY", "SECURITY_MODE"]}],
            )
            == ""
        )
        assert (
            db.create_template(
                "hardening",
                name="Hardening",
                settings={"SECURITY_MODE": "block"},
                steps=[{"title": "S", "settings": ["SECURITY_MODE"]}],
            )
            == ""
        )

    def test_single_element_list_is_unchanged(self, db):
        """THE ACCEPTANCE BAR: one id behaves exactly as it always did."""
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "yes"
        assert cfg["app2.example.com_SECURITY_MODE"]["value"] == "audit"
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["template"] == "base"

    def test_explicit_service_value_beats_every_layer(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)  # app1 explicitly sets SECURITY_MODE=block (method manual)
        self._layers(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="hardening base")
        cfg = db.get_config(methods=True)
        # "base" is last and says audit, but the service's own row wins over every layer.
        assert cfg["app1.example.com_SECURITY_MODE"]["value"] == "block"


class TestGetConfigMultipleGroupRematerialisation:
    """The `multiple`-group re-materialisation block, which `get_config` runs AFTER the overlay.

    It rebuilds every member of a live slot so the scheduler round-trip sees the whole group.
    It used to hand the window's RAW `USE_TEMPLATE` value to `filter_by(template_id=...)`, which
    matches no row at all once the value names more than one layer -- so every member silently
    fell back to its plugin default -- and then wrote that whole list into the per-key `template`
    provenance, where every consumer reads a single template id."""

    @staticmethod
    def _layers(db):
        # REVERSE_PROXY_URL is seeded as a `multiple` member of group "reverse-proxy".
        add_setting(db, "REVERSE_PROXY_HOST", context="multisite", multiple="reverse-proxy", default="")
        assert (
            db.create_template(
                "base",
                name="Base",
                settings={"REVERSE_PROXY_URL_1": "/from-base"},
                steps=[{"title": "S", "settings": ["REVERSE_PROXY_URL_1"]}],
            )
            == ""
        )
        assert (
            db.create_template(
                "hard",
                name="Hard",
                settings={"REVERSE_PROXY_URL_1": "/from-hard"},
                steps=[{"title": "S", "settings": ["REVERSE_PROXY_URL_1"]}],
            )
            == ""
        )

    def test_single_layer_is_unchanged(self, db):
        """THE ACCEPTANCE BAR for this block."""
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["value"] == "/from-base"
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["template"] == "base"
