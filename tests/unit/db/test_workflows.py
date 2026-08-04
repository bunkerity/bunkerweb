"""Workflow resource CRUD, definition storage, attachment and per-service budgets."""

from json import loads

from fixtures.seed import add_global_value, add_service, add_service_setting, seed_minimal, session
from model import Plugins, ResourceAttachments, ResourceGroupUsages, Resources, Settings, Workflows  # type: ignore
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


def _challenge_rule(provider="hcaptcha", rule_id="c1"):
    return {
        "id": rule_id,
        "name": "challenge",
        "enabled": True,
        "condition": {"op": "uri", "match": "prefix", "value": "/login"},
        "action": {"type": "challenge", "provider": provider},
        "threshold": None,
    }


def _seed_antibot_settings(db, *, service_id=None, sitekey="site", secret="secret"):
    """Give a service (or the global scope) the hCaptcha credentials."""
    with session(db) as s:
        s.add(Plugins(id="antibot", name="Antibot", description="Antibot.", version="1.0"))
        s.flush()
        for setting_id in ("ANTIBOT_HCAPTCHA_SITEKEY", "ANTIBOT_HCAPTCHA_SECRET"):
            s.add(
                Settings(
                    id=setting_id,
                    name=setting_id,
                    plugin_id="antibot",
                    context="multisite",
                    default="",
                    help="h",
                    label=setting_id,
                    regex="^.*$",
                    type="password",
                )
            )
    for setting_id, value in (("ANTIBOT_HCAPTCHA_SITEKEY", sitekey), ("ANTIBOT_HCAPTCHA_SECRET", secret)):
        if service_id:
            add_service_setting(db, service_id=service_id, setting_id=setting_id, value=value)
        else:
            add_global_value(db, setting_id=setting_id, value=value)


def test_attaching_a_challenge_workflow_without_credentials_is_refused(db):
    """Otherwise the fail-closed compiler aborts the push for the WHOLE deployment."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _seed_antibot_settings(db, sitekey="", secret="")
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_challenge_rule()))[0] == ""

    error = db.attach_workflow(resource_id, "app1.example.com")
    assert "cannot serve a hcaptcha challenge" in error and "ANTIBOT_HCAPTCHA_SITEKEY" in error
    assert db.get_workflow_details(resource_id)["services"] == []


def test_a_challenge_workflow_attaches_when_the_service_has_the_credentials(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _seed_antibot_settings(db, service_id="app1.example.com")
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_challenge_rule()))[0] == ""

    assert db.attach_workflow(resource_id, "app1.example.com") == ""


def test_clearing_the_credentials_is_caught_when_the_definition_is_saved(db):
    """The save path checks too — attaching first and adding the rule later must not slip through."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _seed_antibot_settings(db, sitekey="", secret="")
    resource_id = _create(db)
    assert db.attach_workflow(resource_id, "app1.example.com") == ""

    error, _ = db.save_workflow_definition(resource_id, _definition(_challenge_rule()))
    assert "cannot serve a hcaptcha challenge" in error
    assert db.get_workflow_details(resource_id)["definition"]["rules"] == []


def test_a_disabled_challenge_rule_does_not_require_credentials(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _seed_antibot_settings(db, sitekey="", secret="")
    resource_id = _create(db)
    rule = _challenge_rule()
    rule["enabled"] = False
    assert db.save_workflow_definition(resource_id, _definition(rule))[0] == ""
    # A disabled rule is never compiled, so it cannot make the compiler raise.
    assert db.attach_workflow(resource_id, "app1.example.com") == ""


def test_draft_services_are_excluded_from_what_the_compiler_sees(db):
    """A draft renders nothing and its settings are absent from the generated config."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    add_service(db, "draft.example.com", is_draft=True)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_rule()))[0] == ""
    assert db.attach_workflow(resource_id, "draft.example.com") == ""

    # The attachment exists and is visible to the operator...
    assert db.get_workflow_details(resource_id)["services"] == ["draft.example.com"]
    # ...but the compiler never sees it, so it cannot abort the push over a service that
    # was never going to be served.
    assert "draft.example.com" not in db.get_service_workflows()


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


def test_a_draft_service_counts_towards_its_own_budget(db):
    """Its baseline was 0 until publication — then the fail-closed compiler aborted the push for
    the whole deployment, over a service nobody had touched since.

    Draft attachments are invisible to the compiler on purpose, but they all reach it at once
    the moment the service is published, so the budget has to count them from the start.
    """
    seed_minimal(db)
    _seed_workflows_plugin(db)
    add_service(db, "draft.example.com", is_draft=True)
    for index in range(MAX_ACTIVE_RULES_PER_SERVICE // MAX_RULES_PER_WORKFLOW):
        resource_id = _create(db, name=f"draft-bulk-{index}")
        rules = [_rule(f"{resource_id}-{number}") for number in range(MAX_RULES_PER_WORKFLOW)]
        assert db.save_workflow_definition(resource_id, _definition(*rules))[0] == ""
        assert db.attach_workflow(resource_id, "draft.example.com") == ""

    extra = _create(db, name="draft-one-too-many")
    assert db.save_workflow_definition(extra, _definition(_rule()))[0] == ""
    error = db.attach_workflow(extra, "draft.example.com")
    assert "active workflow rules" in error and str(MAX_ACTIVE_RULES_PER_SERVICE) in error
    with session(db) as s:
        assert s.query(ResourceAttachments).filter_by(resource_id=extra).count() == 0

    # The compiler's view is unchanged: drafts stay out of it.
    assert "draft.example.com" not in db.get_service_workflows()


def test_a_published_service_budget_is_unaffected_by_drafts(db):
    """The baseline is a per-service bucket, so counting drafts cannot leak into a live service."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    add_service(db, "draft.example.com", is_draft=True)
    bulky = _create(db, name="bulky")
    rules = [_rule(f"r-{number}") for number in range(MAX_RULES_PER_WORKFLOW)]
    assert db.save_workflow_definition(bulky, _definition(*rules))[0] == ""
    assert db.attach_workflow(bulky, "draft.example.com") == ""

    other = _create(db, name="on-the-live-one")
    assert db.save_workflow_definition(other, _definition(_rule()))[0] == ""
    assert db.attach_workflow(other, "app1.example.com") == ""


def test_validate_refuses_what_save_would_refuse(db):
    """The editor validates on every change; a check only save runs is a 400 nobody saw coming."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    _seed_antibot_settings(db, sitekey="", secret="")
    resource_id = _create(db)
    assert db.attach_workflow(resource_id, "app1.example.com") == ""

    canonical, errors = db.validate_workflow_definition(_definition(_challenge_rule()), resource_id=resource_id)
    assert canonical is not None
    assert errors and errors[0]["code"] == "provider_missing" and errors[0]["path"] == "rules"

    # The same triplet on the way out of save, so the editor anchors both the same way.
    error, field_errors = db.save_workflow_definition(resource_id, _definition(_challenge_rule()))
    assert error == errors[0]["message"]
    assert field_errors == errors


def test_a_budget_refusal_is_anchored_for_the_editor(db):
    """Budget errors used to come back with an empty errors array, so nothing could point at them."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    for index in range(MAX_ACTIVE_RULES_PER_SERVICE // MAX_RULES_PER_WORKFLOW):
        resource_id = _create(db, name=f"bulk-{index}")
        rules = [_rule(f"{resource_id}-{number}") for number in range(MAX_RULES_PER_WORKFLOW)]
        assert db.save_workflow_definition(resource_id, _definition(*rules))[0] == ""
        assert db.attach_workflow(resource_id, "app1.example.com") == ""

    extra = _create(db, name="anchored")
    assert db.attach_workflow(extra, "app1.example.com") == ""
    error, field_errors = db.save_workflow_definition(extra, _definition(_rule()))
    assert "active workflow rules" in error
    assert field_errors == [{"path": "rules", "code": "budget_exceeded", "message": error}]


def _tester_rule(rule_id="r1", country="FR", action=None, threshold=None):
    return _rule(rule_id, country=country, action=action, threshold=threshold)


def test_the_tester_sees_the_whole_service_ladder_not_just_this_workflow(db):
    """ "Is my new rule shadowed?" is usually answered by a rule in a *different* workflow."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    first = _create(db, name="edge")
    second = _create(db, name="main")
    for resource_id in (first, second):
        assert db.save_workflow_definition(resource_id, _definition(_tester_rule()))[0] == ""
        assert db.attach_workflow(resource_id, "app1.example.com") == ""

    context, errors = db.test_workflow_definition(second)
    assert errors == []
    assert [entry["id"] for entry in context["workflows"]] == [first, second]
    assert context["service"]["id"] == "app1.example.com" and context["service"]["attached"] is True


def test_the_tester_substitutes_the_unsaved_draft_in_place(db):
    """Position matters, so the candidate replaces the stored one where it already sits."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    other = _create(db, name="first-in-order")
    subject = _create(db, name="second-in-order")
    for resource_id in (other, subject):
        assert db.save_workflow_definition(resource_id, _definition(_tester_rule()))[0] == ""
        assert db.attach_workflow(resource_id, "app1.example.com") == ""

    draft = _definition(_tester_rule("draft-rule", country="BE"))
    context, errors = db.test_workflow_definition(subject, definition=draft)
    assert errors == []
    entries = {entry["id"]: entry for entry in context["workflows"]}
    assert entries[subject]["definition"]["rules"][0]["id"] == "draft-rule"
    # The stored workflow ahead of it is untouched, and still ahead of it.
    assert [entry["id"] for entry in context["workflows"]] == [other, subject]


def test_the_tester_reports_an_invalid_draft_like_validate_does(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)
    context, errors = db.test_workflow_definition(resource_id, definition={"schema_version": 1, "rules": [{"id": "r1"}]})
    assert context is None and errors and errors[0]["path"].startswith("rules[0]")


def test_the_tester_reads_the_services_security_mode_and_deny_status(db):
    """Reporting "blocks with 403" against a service in detect mode is wrong in the worst way."""
    seed_minimal(db)
    _seed_workflows_plugin(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="SECURITY_MODE", value="detect")
    add_global_value(db, setting_id="DENY_HTTP_STATUS", value="444")
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_tester_rule()))[0] == ""
    assert db.attach_workflow(resource_id, "app1.example.com") == ""

    context, _ = db.test_workflow_definition(resource_id)
    assert context["service"]["security_mode"] == "detect"
    assert context["service"]["deny_status"] == 444


def test_the_tester_says_a_draft_service_compiles_to_nothing(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    add_service(db, "draft.example.com", is_draft=True)
    resource_id = _create(db)
    assert db.save_workflow_definition(resource_id, _definition(_tester_rule()))[0] == ""
    assert db.attach_workflow(resource_id, "draft.example.com") == ""

    context, errors = db.test_workflow_definition(resource_id, service_id="draft.example.com")
    assert errors == [] and context["service"]["is_draft"] is True
    assert context["workflows"] == []


def test_the_tester_reports_no_service_when_the_workflow_is_attached_nowhere(db):
    seed_minimal(db)
    _seed_workflows_plugin(db)
    resource_id = _create(db)
    context, errors = db.test_workflow_definition(resource_id)
    assert errors == [] and context["service"] is None
