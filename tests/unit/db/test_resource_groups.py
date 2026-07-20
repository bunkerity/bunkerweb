"""DatabaseResourceGroupsMixin — resource group create/get/update/delete + validation."""

from fixtures.seed import (
    add_global_value,
    add_service_setting,
    add_setting,
    seed_minimal,
)


def _entries():
    return [
        {"kind": "ip", "value": "203.0.113.5", "comment": "office"},
        {"kind": "ip", "value": "198.51.100.0/24"},
        {"kind": "country", "value": "fr", "comment": "HQ"},
        {"kind": "asn", "value": "AS32934"},
    ]


def _add_resource_setting(db):
    add_setting(db, "BLACKLIST_IP", context="multisite", type="multivalue")


class TestCreateAndGet:
    def test_create_and_get(self, db):
        assert db.create_resource_group("office", name="Office", description="corp", entries=_entries()) == ""
        groups = db.get_resource_groups()
        assert "office" in groups
        g = groups["office"]
        assert g["name"] == "Office"
        assert g["description"] == "corp"
        assert g["method"] == "ui"
        # normalization: country uppercased, ASN prefix stripped
        kv = {(e["kind"], e["value"]) for e in g["entries"]}
        assert ("ip", "203.0.113.5") in kv
        assert ("country", "FR") in kv
        assert ("asn", "32934") in kv
        # per-entry comment preserved
        ip_entry = next(e for e in g["entries"] if e["value"] == "203.0.113.5")
        assert ip_entry["comment"] == "office"

    def test_duplicate_id_rejected(self, db):
        db.create_resource_group("office", name="Office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        msg = db.create_resource_group("office", name="Office2", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        assert msg == "Resource group office already exists"

    def test_duplicate_name_rejected(self, db):
        db.create_resource_group("g1", name="Same", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        msg = db.create_resource_group("g2", name="Same", entries=[{"kind": "ip", "value": "5.6.7.8"}])
        assert msg == "Resource group name Same already exists"

    def test_empty_id_rejected(self, db):
        assert db.create_resource_group("   ", name="X", entries=[]) == "Resource group id is required"

    def test_empty_name_rejected(self, db):
        assert db.create_resource_group("g", name="  ", entries=[]) == "Resource group name cannot be empty"

    def test_alias_grammar_is_enforced_at_db_boundary(self, db):
        message = db.create_resource_group("bad alias", name="bad alias", entries=[])
        assert "must contain 1 to 64" in message

    def test_builtin_alias_is_reserved_for_user_groups(self, db):
        assert db.create_resource_group("EU", name="EU", entries=[]) == "Resource group id is reserved by BunkerWeb"

    def test_builtin_alias_is_allowed_for_managed_groups(self, db):
        assert db.create_resource_group("eu", name="EU", entries=[], method="manual") == ""

    def test_empty_entries_allowed(self, db):
        assert db.create_resource_group("empty", name="Empty", entries=[]) == ""
        assert db.get_resource_groups()["empty"]["entries"] == []

    def test_dedupes_entries(self, db):
        entries = [
            {"kind": "ip", "value": "1.2.3.4"},
            {"kind": "ip", "value": "1.2.3.4", "comment": "dup"},
            {"kind": "country", "value": "FR"},
        ]
        assert db.create_resource_group("g", name="G", entries=entries) == ""
        g = db.get_resource_groups()["g"]
        assert len(g["entries"]) == 2


class TestEntryValidation:
    def test_invalid_kind_rejected(self, db):
        msg = db.create_resource_group("g", name="G", entries=[{"kind": "port", "value": "80"}])
        assert "Invalid entry kind" in msg

    def test_invalid_ip_rejected(self, db):
        msg = db.create_resource_group("g", name="G", entries=[{"kind": "ip", "value": "not-an-ip"}])
        assert "Invalid ip value" in msg

    def test_invalid_country_rejected(self, db):
        msg = db.create_resource_group("g", name="G", entries=[{"kind": "country", "value": "FRA"}])
        assert "Invalid country value" in msg

    def test_user_agent_is_free_form(self, db):
        assert db.create_resource_group("g", name="G", entries=[{"kind": "user_agent", "value": "(?i)badbot"}]) == ""

    def test_whitespace_in_runtime_pattern_is_rejected(self, db):
        message = db.create_resource_group("g", name="G", entries=[{"kind": "user_agent", "value": "Mozilla Firefox"}])
        assert "Invalid user_agent value" in message

    def test_entry_count_limit_is_enforced(self, db):
        message = db.create_resource_group("g", name="G", entries=[{}] * 5001)
        assert "more than 5000" in message

    def test_entry_value_and_comment_limits_are_enforced(self, db):
        value_message = db.create_resource_group("g", name="G", entries=[{"kind": "uri", "value": "x" * 8193}])
        comment_message = db.create_resource_group(
            "g",
            name="G",
            entries=[{"kind": "uri", "value": "x", "comment": "x" * 1001}],
        )
        assert "values cannot exceed 8192" in value_message
        assert "comments cannot exceed 1000" in comment_message

    def test_description_limit_is_enforced(self, db):
        message = db.create_resource_group("g", name="G", description="x" * 4001, entries=[])
        assert "descriptions cannot exceed 4000" in message


class TestDetailsAndUpdate:
    def test_details(self, db):
        db.create_resource_group("office", name="Office", entries=_entries())
        details = db.get_resource_group_details("office")
        assert details["id"] == "office"
        assert details["name"] == "Office"
        assert len(details["entries"]) == 4

    def test_details_missing(self, db):
        assert db.get_resource_group_details("ghost") is None

    def test_update_entries(self, db):
        db.create_resource_group("office", name="Office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        assert db.update_resource_group("office", entries=[{"kind": "country", "value": "DE"}]) == ""
        g = db.get_resource_groups()["office"]
        assert g["name"] == "Office"
        assert [(e["kind"], e["value"]) for e in g["entries"]] == [("country", "DE")]

    def test_alias_cannot_be_renamed(self, db):
        db.create_resource_group("office", name="Office", entries=[])
        assert "cannot be modified" in db.update_resource_group("office", name="HQ")
        assert db.get_resource_groups()["office"]["name"] == "Office"

    def test_update_keeps_entries_when_omitted(self, db, monkeypatch):
        db.create_resource_group("office", name="Office", entries=[{"kind": "ip", "value": "1.2.3.4"}])

        def fail_if_entries_are_touched(_entries):
            raise AssertionError("entries must remain untouched")

        monkeypatch.setattr(db, "_prepare_group_entries", fail_if_entries_are_touched)
        assert db.update_resource_group("office", description="new desc") == ""
        g = db.get_resource_groups()["office"]
        assert g["description"] == "new desc"
        assert [(e["kind"], e["value"]) for e in g["entries"]] == [("ip", "1.2.3.4")]

    def test_update_missing(self, db):
        assert db.update_resource_group("ghost", name="X") == "Resource group not found"


class TestDelete:
    def test_delete(self, db):
        db.create_resource_group("office", name="Office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        assert db.delete_resource_group("office") == ""
        assert "office" not in db.get_resource_groups()

    def test_delete_missing(self, db):
        assert db.delete_resource_group("ghost") == "Resource group not found"

    def test_delete_blocked_when_referenced(self, db):
        seed_minimal(db)
        _add_resource_setting(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        add_global_value(db, setting_id="BLACKLIST_IP", value="@office")
        assert db.delete_resource_group("office") == "Resource group office is currently referenced by a setting"

    def test_delete_blocked_when_template_references_group(self, db):
        seed_minimal(db)
        _add_resource_setting(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        assert (
            db.create_template(
                "security",
                name="Security",
                settings={"BLACKLIST_IP": "@office"},
                steps=[{"title": "Security", "settings": ["BLACKLIST_IP"]}],
            )
            == ""
        )
        assert db.delete_resource_group("office") == "Resource group office is currently referenced by a setting"

    def test_delete_not_blocked_by_similar_token(self, db):
        seed_minimal(db)
        _add_resource_setting(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        # Only an exact whitespace-delimited @office token is a reference.
        add_global_value(
            db,
            setting_id="BLACKLIST_IP",
            value="@office2 (@office) @office,",
        )
        assert db.delete_resource_group("office") == ""

    def test_delete_not_blocked_by_incompatible_setting(self, db):
        seed_minimal(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        add_global_value(db, setting_id="USE_REVERSE_PROXY", value="@office")
        assert db.delete_resource_group("office") == ""


class TestReferences:
    def test_global_and_service_reference_details(self, db):
        seeded = seed_minimal(db)
        _add_resource_setting(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        add_global_value(db, setting_id="BLACKLIST_IP", value="@office")
        add_service_setting(
            db,
            service_id=seeded["service_id"],
            setting_id="BLACKLIST_IP",
            value="literal @office",
        )

        references = db.get_resource_group_references("office")["office"]

        assert references == [
            {
                "scope": "global",
                "service_id": None,
                "setting_id": "BLACKLIST_IP",
                "suffix": 0,
                "method": "scheduler",
                "plugin_id": "general",
            },
            {
                "scope": "service",
                "service_id": seeded["service_id"],
                "setting_id": "BLACKLIST_IP",
                "suffix": 0,
                "method": "manual",
                "plugin_id": "general",
            },
        ]

    def test_reference_details_respect_token_boundary(self, db):
        seed_minimal(db)
        _add_resource_setting(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        add_global_value(db, setting_id="BLACKLIST_IP", value="@office2")

        assert db.get_resource_group_references("office") == {"office": []}

    def test_template_reference_details(self, db):
        seed_minimal(db)
        _add_resource_setting(db)
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        db.create_template(
            "security",
            name="Security",
            settings={"BLACKLIST_IP": "@office"},
            steps=[{"title": "Security", "settings": ["BLACKLIST_IP"]}],
        )

        assert db.get_resource_group_references("office")["office"] == [
            {
                "scope": "template",
                "service_id": None,
                "template_id": "security",
                "template_name": "Security",
                "setting_id": "BLACKLIST_IP",
                "suffix": 0,
                "method": "ui",
                "plugin_id": "general",
            }
        ]


class TestImmutability:
    def test_core_group_cannot_be_updated(self, db):
        db.create_resource_group(
            "eu",
            name="eu",
            entries=[{"kind": "country", "value": "FR"}],
            method="manual",
        )
        msg = db.update_resource_group("eu", entries=[{"kind": "country", "value": "DE"}])
        assert msg == "This resource group is provided by BunkerWeb and cannot be modified"

    def test_core_group_cannot_be_deleted(self, db):
        db.create_resource_group(
            "eu",
            name="eu",
            entries=[{"kind": "country", "value": "FR"}],
            method="manual",
        )
        assert db.delete_resource_group("eu") == "This resource group is provided by BunkerWeb and cannot be deleted"


class TestPluginAndReadonly:
    def test_plugin_id_valid(self, db):
        seed_minimal(db)
        assert (
            db.create_resource_group(
                "g",
                name="G",
                entries=[{"kind": "ip", "value": "1.2.3.4"}],
                plugin_id="general",
            )
            == ""
        )
        assert db.get_resource_groups()["g"]["plugin_id"] == "general"

    def test_plugin_id_unknown_rejected(self, db):
        msg = db.create_resource_group(
            "g",
            name="G",
            entries=[{"kind": "ip", "value": "1.2.3.4"}],
            plugin_id="ghost",
        )
        assert msg == "Plugin ghost does not exist"

    def test_readonly_blocks_create(self, db):
        db.readonly = True
        try:
            msg = db.create_resource_group("g", name="G", entries=[{"kind": "ip", "value": "1.2.3.4"}])
        finally:
            db.readonly = False
        assert msg == "The database is read-only, the changes will not be saved"
