"""DatabaseConfigReadMixin — setting validation and the multisite config assembly.

The multisite brain: prefixing, suffix expansion, per-service override precedence and
the global -> per-service default propagation. Uses ``seed_multisite``.
"""

from fixtures.seed import add_select_setting, add_setting, seed_minimal, seed_multisite


class TestIsValidSetting:
    def test_valid_global(self, db):
        seed_minimal(db)
        assert db.is_valid_setting("MULTISITE", value="yes") == (True, "")

    def test_regex_mismatch(self, db):
        seed_minimal(db)
        ok, msg = db.is_valid_setting("MULTISITE", value="maybe")
        assert ok is False
        assert "not matching regex" in msg

    def test_check_aliases_and_service_prefixes(self, db):
        seed_minimal(db)
        assert db.is_valid_setting("MULTISITE", value="on") == (True, "")
        assert db.is_valid_setting("MULTISITE", value="disabled") == (True, "")
        assert db.is_valid_setting("SECURITY_MODE", value="on") == (True, "")
        assert db.is_valid_setting("app1.example.com_USE_REVERSE_PROXY", value="on", extra_services=["app1.example.com"]) == (True, "")
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

    def test_unit_values_use_authoritative_parser(self, db):
        seed_minimal(db)
        add_setting(db, "MEM_SIZE", type="size", regex=r"^\d+([kKmMgG])?$", default="0")
        add_setting(db, "MY_TIMEOUT", type="duration", regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", default="0")

        assert db.is_valid_setting("MEM_SIZE", value="64 M") == (True, "")
        assert db.is_valid_setting("MEM_SIZE", value="1.5g")[0] is False
        assert db.is_valid_setting("MY_TIMEOUT", value="1h 30min") == (True, "")
        assert db.is_valid_setting("MY_TIMEOUT", value="30x")[0] is False
        assert db.is_valid_setting("MY_TIMEOUT", value="30m1h")[0] is False

    def test_empty_unit_values_are_decided_by_the_setting_regex(self, db):
        seed_minimal(db)
        add_setting(db, "OPTIONAL_SIZE", type="size", regex=r"^(\d+([kKmMgG])?)?$", default="")
        add_setting(db, "OPTIONAL_TIMEOUT", type="duration", regex=r"^((\d+(ms|s|m|h|d|w|M|y))+|\d+)?$", default="")

        assert db.is_valid_setting("OPTIONAL_SIZE", value="") == (True, "")
        assert db.is_valid_setting("OPTIONAL_TIMEOUT", value="") == (True, "")

    def test_service_prefixed_global_setting_rejected(self, db):
        seed_minimal(db)
        # A global setting addressed with a known service prefix resolves via the DB
        # services scan, which flips multisite=True -> 'not multisite'.
        assert db.is_valid_setting("app1.example.com_MULTISITE") == (False, "not multisite")

    def test_scalar_and_select_values_are_normalized(self, db):
        seed_minimal(db)
        add_setting(db, "TEST_PORT", type="number", regex=r"^\d+$", default="0")
        add_setting(db, "TEST_PICK", type="select", regex=r"^(a|b)$", default="a")
        add_select_setting(db, "CIPHERS", ["modern", "intermediate", "old"], default="modern", case_insensitive=True)
        add_select_setting(db, "SEC_ENGINE", ["On", "DetectionOnly", "Off"], default="On", case_insensitive=False)
        add_select_setting(db, "PARTS", ["alpha", "beta"], regex=r"^( *(alpha|beta) *)*$", default="", case_insensitive=True, multiselect=True)

        assert db.is_valid_setting("TEST_PORT", value="8080 ") == (True, "")
        assert db.is_valid_setting("TEST_PORT", value="  ")[0] is False
        assert db.is_valid_setting("TEST_PICK", value=" a ") == (True, "")
        assert db.is_valid_setting("SECURITY_MODE", value="  on  ") == (True, "")
        assert db.is_valid_setting("CIPHERS", value="Modern") == (True, "")
        assert db.is_valid_setting("CIPHERS", value="moderns")[0] is False
        assert db.is_valid_setting("SEC_ENGINE", value="On") == (True, "")
        assert db.is_valid_setting("SEC_ENGINE", value="on")[0] is False
        assert db.is_valid_setting("PARTS", value="ALPHA Beta") == (True, "")


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

    def test_last_layer_wins_on_a_shared_key(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base hardening")
        cfg = db.get_config(methods=True)
        # shared key -> the LAST layer
        assert cfg["app2.example.com_SECURITY_MODE"]["value"] == "block"
        assert cfg["app2.example.com_SECURITY_MODE"]["template"] == "hardening"
        # key only the first layer defines -> survives
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "yes"
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["template"] == "base"

    def test_order_is_significant(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="hardening base")
        cfg = db.get_config(methods=True)
        # "audit" is base's own value and is set nowhere else, so this cannot pass on the global.
        assert cfg["app2.example.com_SECURITY_MODE"]["value"] == "audit"
        assert cfg["app2.example.com_SECURITY_MODE"]["template"] == "base"

    def test_each_service_gets_its_own_order(self, db):
        """The overlay used to iterate PER TEMPLATE, which cannot express this: two services
        sharing the same two layers in opposite orders would both get whichever order the outer
        loop happened to visit.

        Uses two FRESH services -- seed_multisite gives app1 explicit rows for both keys, which
        beat every layer and would mask the ordering entirely."""
        from fixtures.seed import add_service, add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service(db, "app3.example.com")
        add_service(db, "app4.example.com")
        add_service_setting(db, service_id="app3.example.com", setting_id="USE_TEMPLATE", value="base hardening")
        add_service_setting(db, service_id="app4.example.com", setting_id="USE_TEMPLATE", value="hardening base")
        cfg = db.get_config(methods=True)

        # Same two layers, opposite orders -> opposite winners, in ONE get_config call.
        assert cfg["app3.example.com_SECURITY_MODE"]["value"] == "block"
        assert cfg["app3.example.com_SECURITY_MODE"]["template"] == "hardening"
        assert cfg["app4.example.com_SECURITY_MODE"]["value"] == "audit"
        assert cfg["app4.example.com_SECURITY_MODE"]["template"] == "base"

    def test_explicit_service_value_beats_every_layer(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)  # app1 explicitly sets SECURITY_MODE=block (method manual)
        self._layers(db)
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="hardening base")
        cfg = db.get_config(methods=True)
        # "base" is last and says audit, but the service's own row wins over every layer.
        assert cfg["app1.example.com_SECURITY_MODE"]["value"] == "block"

    def test_unknown_layer_is_skipped_not_fatal(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base nope hardening")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_SECURITY_MODE"]["value"] == "block"
        assert cfg["app2.example.com_USE_REVERSE_PROXY"]["value"] == "yes"

    def test_global_template_list_applies_in_order(self, db):
        from fixtures.seed import add_global_value

        seed_minimal(db)
        self._layers(db)
        add_global_value(db, setting_id="USE_TEMPLATE", value="base hardening")
        cfg = db.get_config(methods=True)
        assert cfg["SECURITY_MODE"]["value"] == "block"
        assert cfg["SECURITY_MODE"]["template"] == "hardening"
        assert cfg["USE_REVERSE_PROXY"]["template"] == "base"


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

    def test_a_multi_layer_value_still_resolves_the_member(self, db):
        """With one id this always worked; with two it matched nothing and served the plugin
        default instead."""
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base hard")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["value"] == "/from-hard"

    def test_the_provenance_is_the_owning_layer_not_the_whole_list(self, db):
        """`'template': 'base hard'` is not a template id -- the UI's provenance checks and
        save_scope's outgoing-template rule both compare it against one."""
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base hard")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["template"] == "hard"

    def test_order_selects_the_owning_layer(self, db):
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="hard base")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["value"] == "/from-base"
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["template"] == "base"

    def test_a_member_no_layer_supplies_has_no_template_provenance(self, db):
        """A PLUGIN default is not template-provided. Claiming a layer for it makes
        save_scope.restore_unowned_settings treat it as an outgoing template value and drop it on
        a template change -- which is why `None` here is load-bearing, not cosmetic."""
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base hard")
        cfg = db.get_config(methods=True)
        # REVERSE_PROXY_HOST_1 is a sibling of the live slot that NO layer defines.
        sibling = cfg["app2.example.com_REVERSE_PROXY_HOST_1"]
        assert sibling["template"] is None
        assert sibling["value"] == ""

    def test_the_service_scoped_route_reaches_this_block_and_resolves_per_layer(self, db):
        """The live path, and the one that proves this resolution is not defensive code.

        `get_config(service=...)` POPS every key and re-adds only the `{service}_`-prefixed ones,
        so a group member the GLOBAL overlay wrote is gone from `config` by the time this block
        runs -- and this block re-materialises it. Under the pre-fix code the same call did
        `filter_by(template_id="g1 g2")`, matched nothing, and served the plugin default.

        Note the pre-existing shape this pins: under `service=` the key has already had its
        prefix stripped when the window is chosen, so `window` stays "global" and the member is
        resolved against the GLOBAL layer list even though the service carries its own.
        """
        from fixtures.seed import add_global_value, add_service, add_service_setting

        seed_multisite(db)
        add_setting(db, "REVERSE_PROXY_HOST", context="multisite", multiple="reverse-proxy", default="")
        for layer, value in (("g1", "/from-g1"), ("g2", "/from-g2")):
            assert (
                db.create_template(
                    layer,
                    name=layer.upper(),
                    settings={"REVERSE_PROXY_HOST_1": value},
                    steps=[{"title": "S", "settings": ["REVERSE_PROXY_HOST_1"]}],
                )
                == ""
            )
        assert (
            db.create_template("svc", name="Svc", settings={"USE_REVERSE_PROXY": "yes"}, steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}])
            == ""
        )

        add_global_value(db, setting_id="USE_TEMPLATE", value="g1 g2")
        add_service(db, "app3.example.com")
        add_service_setting(db, service_id="app3.example.com", setting_id="USE_TEMPLATE", value="svc")
        # A prefixed suffixed row keeps slot 1 alive once the prefix is stripped, which is what
        # puts "reverse-proxy" into `multiple` and makes the block run at all.
        add_service_setting(db, service_id="app3.example.com", setting_id="REVERSE_PROXY_URL", value="/api", suffix=1)

        cfg = db.get_config(methods=True, service="app3.example.com")
        member = cfg["REVERSE_PROXY_HOST_1"]
        assert member["value"] == "/from-g2", "the global layer list was not resolved last-wins"
        assert member["template"] == "g2", "provenance must be the owning LAYER, not the list"

    def test_single_layer_is_unchanged(self, db):
        """THE ACCEPTANCE BAR for this block."""
        from fixtures.seed import add_service_setting

        seed_multisite(db)
        self._layers(db)
        add_service_setting(db, service_id="app2.example.com", setting_id="USE_TEMPLATE", value="base")
        cfg = db.get_config(methods=True)
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["value"] == "/from-base"
        assert cfg["app2.example.com_REVERSE_PROXY_URL_1"]["template"] == "base"
