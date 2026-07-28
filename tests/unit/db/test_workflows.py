"""Workflow resource CRUD, definition storage, attachment and per-service budgets."""

from json import loads

from fixtures.seed import add_service, seed_minimal, session
from model import Plugins, ResourceAttachments, ResourceGroupUsages, Resources, Workflows  # type: ignore
from workflow_schema import MAX_ACTIVE_RULES_PER_SERVICE, MAX_RULES_PER_WORKFLOW, canonical_json  # type: ignore


def _seed_workflows_plugin(db) -> None:
    """Register the ``workflows`` core plugin.

    The mixin flags this row ``config_changed`` on every mutation that alters what the
    compiler would emit, so a test skipping this seed silently exercises the no-op path.
    """
    with session(db) as s:
        s.add(Plugins(id="workflows", name="Workflows", description="Security workflows.", version="1.0"))


def _rule(rule_id="r1", country="FR", action=None, threshold=None):
    return {
        "id": rule_id,
        "name": f"rule {rule_id}",
        "enabled": True,
        "condition": {"op": "country", "values": [country]},
        "action": action or {"type": "block"},
        "threshold": threshold,
    }


def _definition(*rules):
    return {"schema_version": 1, "rules": list(rules)}


def _create(db, *, name="login-protection", **kwargs):
    resource_id, error = db.create_workflow(name=name, **kwargs)
    assert error == ""
    return resource_id


def _config_changed(db) -> bool:
    with session(db) as s:
        return bool(s.get(Plugins, "workflows").config_changed)


def _clear_config_changed(db) -> None:
    with session(db) as s:
        s.get(Plugins, "workflows").config_changed = False


def test_create_list_and_details(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db, description="Protects the login form")

    listing = db.get_workflows()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert (item["id"], item["name"], item["description"]) == (resource_id, "login-protection", "Protects the login form")
    assert (item["rules_count"], item["services"]) == (0, [])

    details = db.get_workflow_details(resource_id)
    assert details["definition"] == {"schema_version": 1, "rules": []}
    assert db.get_workflow_details("missing") is None

    with session(db) as s:
        assert s.get(Resources, resource_id).type == "workflow"
        assert s.get(Workflows, resource_id).schema_version == 1


def test_create_is_not_a_config_change_until_attached(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _create(db)
    # A workflow attached to nothing compiles to nothing; flagging it would cost every
    # instance a pointless reload.
    assert _config_changed(db) is False


def test_duplicate_name_is_refused(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _create(db)
    _, error = db.create_workflow(name="login-protection")
    assert "already exists" in error


def test_definition_is_stored_canonically(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)

    error, field_errors = db.save_workflow_definition(resource_id, _definition(_rule(country="fr")))
    assert (error, field_errors) == ("", [])

    with session(db) as s:
        raw = s.get(Workflows, resource_id).definition
    # Canonical: sorted keys, no whitespace — re-serialising the parsed document is a
    # no-op, which is what the artefact checksum depends on.
    assert raw == canonical_json(loads(raw))
    assert loads(raw)["rules"][0]["condition"]["values"] == ["FR"]  # upper-cased on the way in
    assert db.get_workflow_details(resource_id)["rules_count"] == 1


def test_an_invalid_definition_is_refused_with_anchored_errors(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)

    error, field_errors = db.save_workflow_definition(resource_id, _definition(_rule(country="NOPE")))
    assert error and field_errors[0]["code"] == "country_invalid"
    assert field_errors[0]["path"].startswith("rules[0].condition")
    # Nothing was written: the previous definition survives a rejected save.
    assert db.get_workflow_details(resource_id)["definition"] == {"schema_version": 1, "rules": []}


def test_a_definition_referencing_a_missing_group_is_refused(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)
    rule = _rule()
    rule["condition"] = {"op": "group", "kind": "ip", "group_id": "ghost"}

    error, field_errors = db.save_workflow_definition(resource_id, _definition(rule))
    assert field_errors[0]["code"] == "group_missing" and "ghost" in error


def test_a_group_is_referenced_by_id_not_by_name(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    assert db.create_resource_group("office-ips", name="office_ips", entries=[{"kind": "ip", "value": "203.0.113.0/24"}]) == ""
    resource_id = _create(db)

    rule = _rule()
    rule["condition"] = {"op": "group", "kind": "ip", "group_id": "office-ips"}
    assert db.save_workflow_definition(resource_id, _definition(rule))[0] == ""

    # The alias is not an accepted reference: renaming a group must never silently repoint
    # a security rule at another one.
    by_name = _rule()
    by_name["condition"] = {"op": "group", "kind": "ip", "group_id": "office_ips"}
    assert db.save_workflow_definition(resource_id, _definition(by_name))[1][0]["code"] == "group_missing"


def test_saving_flags_a_config_change_only_when_attached(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)

    assert db.save_workflow_definition(resource_id, _definition(_rule()))[0] == ""
    assert _config_changed(db) is False

    assert db.attach_workflow(resource_id, "app1.example.com") == ""
    assert _config_changed(db) is True
    _clear_config_changed(db)

    assert db.save_workflow_definition(resource_id, _definition(_rule(country="BE")))[0] == ""
    assert _config_changed(db) is True


def test_renaming_is_not_a_config_change(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)
    assert db.attach_workflow(resource_id, "app1.example.com") == ""
    _clear_config_changed(db)

    # Rules reference resources by id, so a rename changes nothing the runtime reads.
    assert db.update_workflow(resource_id, name="renamed", description="d") == ""
    assert _config_changed(db) is False


def test_attach_is_idempotent_and_detach_is_reported(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)

    assert db.attach_workflow(resource_id, "app1.example.com") == ""
    _clear_config_changed(db)
    assert db.attach_workflow(resource_id, "app1.example.com") == ""
    assert _config_changed(db) is False  # nothing changed, nothing to signal

    assert db.attach_workflow(resource_id, "ghost.example.com") == "Service not found"
    assert db.get_workflow_details(resource_id)["services"] == ["app1.example.com"]

    assert db.detach_workflow(resource_id, "app1.example.com") == ""
    assert _config_changed(db) is True
    assert db.detach_workflow(resource_id, "app1.example.com") == "Workflow attachment not found"


def test_delete_is_refused_while_attached(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)
    assert db.attach_workflow(resource_id, "app1.example.com") == ""

    assert db.delete_workflow(resource_id) == "Workflow is attached to a service"
    assert db.detach_workflow(resource_id, "app1.example.com") == ""
    assert db.delete_workflow(resource_id) == ""

    with session(db) as s:
        # The typed vertical row goes with the resource.
        assert s.get(Resources, resource_id) is None and s.get(Workflows, resource_id) is None


def test_clone_copies_the_rules_but_not_the_attachments(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_rule()))[0] == ""
    assert db.attach_workflow(resource_id, "app1.example.com") == ""

    clone_id, error = db.clone_workflow(resource_id, name="login-protection-copy")
    assert error == "" and clone_id != resource_id
    clone = db.get_workflow_details(clone_id)
    assert clone["definition"] == db.get_workflow_details(resource_id)["definition"]
    assert clone["services"] == []

    _, error = db.clone_workflow(resource_id, name="login-protection")
    assert "already exists" in error


def test_service_workflows_are_ordered_by_attachment(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    add_service(db, "app2.example.com")
    first = _create(db, name="zzz-attached-first")
    second = _create(db, name="aaa-attached-second")
    assert db.attach_workflow(first, "app1.example.com") == ""
    assert db.attach_workflow(second, "app1.example.com") == ""
    assert db.attach_workflow(second, "app2.example.com") == ""

    per_service = db.get_service_workflows()
    # Attachment order, not name order: the runtime stops at the first effective match, so
    # this ordering decides which rule wins.
    assert [entry["id"] for entry in per_service["app1.example.com"]] == [first, second]
    assert [entry["id"] for entry in per_service["app2.example.com"]] == [second]


def _group_rule(group_id, rule_id="r1"):
    return {
        "id": rule_id,
        "name": "from group",
        "enabled": True,
        "condition": {"op": "group", "kind": "ip", "group_id": group_id},
        "action": {"type": "block"},
        "threshold": None,
    }


def _seed_group(db, group_id="office-ips"):
    assert db.create_resource_group(group_id, name=group_id.replace("-", "_"), entries=[{"kind": "ip", "value": "203.0.113.0/24"}]) == ""
    return group_id


def _usages(db, resource_id):
    with session(db) as s:
        return s.query(ResourceGroupUsages).filter_by(consumer_id=resource_id).count()


def test_a_referenced_group_cannot_be_deleted_and_the_consumer_is_named(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    group_id = _seed_group(db)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_group_rule(group_id)))[0] == ""

    error = db.delete_resource_group(group_id)
    # "Referenced somewhere" is useless when the reference lives inside a rule tree.
    assert "workflows/workflow" in error and "1 object" in error
    assert db.get_resource_group_usages(group_id)[group_id][0]["consumer_id"] == resource_id


def test_dropping_the_reference_releases_the_group(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    group_id = _seed_group(db)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_group_rule(group_id)))[0] == ""
    assert _usages(db, resource_id) == 1

    # Usages are replaced with the definition, in the same transaction.
    assert db.save_workflow_definition(resource_id, _definition(_rule()))[0] == ""
    assert _usages(db, resource_id) == 0
    assert db.delete_resource_group(group_id) == ""


def test_deleting_the_workflow_releases_the_group(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    group_id = _seed_group(db)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_group_rule(group_id)))[0] == ""

    assert db.delete_workflow(resource_id) == ""
    # Usage rows hang off the consumer id, not a foreign key, so nothing cascades them.
    assert _usages(db, resource_id) == 0
    assert db.delete_resource_group(group_id) == ""


def test_a_clone_protects_the_group_it_inherited(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    group_id = _seed_group(db)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_group_rule(group_id)))[0] == ""
    clone_id, error = db.clone_workflow(resource_id, name="copy")
    assert error == ""

    assert db.delete_workflow(resource_id) == ""
    assert _usages(db, clone_id) == 1
    assert "workflows/workflow" in db.delete_resource_group(group_id)


def test_editing_a_referenced_group_flags_the_consumer_plugin(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    group_id = _seed_group(db)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_group_rule(group_id)))[0] == ""
    _clear_config_changed(db)

    # No workflow row moved, but what the compiler emits just changed.
    assert db.update_resource_group(group_id, entries=[{"kind": "ip", "value": "198.51.100.0/24"}]) == ""
    assert _config_changed(db) is True


def test_a_service_cannot_be_pushed_past_the_aggregate_rule_budget(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    full = [_create(db, name=f"bulk-{index}") for index in range(MAX_ACTIVE_RULES_PER_SERVICE // MAX_RULES_PER_WORKFLOW)]
    for resource_id in full:
        rules = [_rule(f"{resource_id}-{index}") for index in range(MAX_RULES_PER_WORKFLOW)]
        assert db.save_workflow_definition(resource_id, _definition(*rules))[0] == ""
        assert db.attach_workflow(resource_id, "app1.example.com") == ""

    # The per-workflow caps bound one document; this one bounds what a request actually pays.
    extra = _create(db, name="one-too-many")
    assert db.save_workflow_definition(extra, _definition(_rule()))[0] == ""
    error = db.attach_workflow(extra, "app1.example.com")
    assert "active workflow rules" in error and str(MAX_ACTIVE_RULES_PER_SERVICE) in error
    with session(db) as s:
        assert s.query(ResourceAttachments).filter_by(resource_id=extra).count() == 0
