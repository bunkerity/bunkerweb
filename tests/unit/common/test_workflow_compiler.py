"""The workflow compiler: golden artefact, determinism and its fail-closed refusals.

The artefact is the only thing the Lua runtime ever reads, so its exact shape is pinned
here rather than described. It must also be byte-identical across runs — the cache push
ships it by checksum, and an unstable artefact would re-push and reload on every generation.
"""

import json
from pathlib import Path
from sys import path as sys_path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_COMPILER_DIR = ROOT / "src" / "common" / "core" / "workflows" / "config"
if str(_COMPILER_DIR) not in sys_path:
    sys_path.insert(0, str(_COMPILER_DIR))

from compiler import compile_config  # type: ignore  # noqa: E402
from workflow_schema import canonical_json  # type: ignore  # noqa: E402


class _Logger:
    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class FakeDB:
    def __init__(self, attached, groups=None):
        self._attached = attached
        self._groups = groups or {}

    def get_service_workflows(self):
        return self._attached

    def get_resource_groups(self):
        return self._groups


def _definition(*rules):
    return json.dumps({"schema_version": 1, "rules": list(rules)})


def _rule(rule_id="5f1c", condition=None, action=None, threshold=None, enabled=True):
    return {
        "id": rule_id,
        "name": "Login flood challenge",
        "enabled": enabled,
        "condition": condition or {"op": "all", "nodes": [{"op": "country", "values": ["FR"]}, {"op": "uri", "match": "prefix", "value": "/login"}]},
        "action": action or {"type": "challenge", "provider": "hcaptcha"},
        "threshold": threshold if threshold is not None else {"count": 10, "window": 60, "key": "ip"},
    }


def _attached(definition, workflow_id="wf-7c3e", server="app.example.com", name="Login protection"):
    return {server: [{"id": workflow_id, "name": name, "schema_version": 1, "definition": definition}]}


def _config(**extra):
    return {
        "MULTISITE": "yes",
        "SERVER_NAME": "app.example.com",
        "ANTIBOT_HCAPTCHA_SITEKEY": "site",
        "ANTIBOT_HCAPTCHA_SECRET": "secret",
        **extra,
    }


def test_the_artefact_matches_the_documented_shape():
    result = compile_config(FakeDB(_attached(_definition(_rule()))), _config(), _Logger())

    assert result["data"] == {
        "schema_version": 1,
        "groups": {},
        "services": {"app.example.com": ["wf-7c3e"]},
        "workflows": {
            "wf-7c3e": {
                "name": "Login protection",
                "rules": [
                    {
                        "id": "5f1c",
                        "counter": "wf-7c3e/5f1c",
                        "condition": {"op": "all", "nodes": [{"op": "country", "values": ["FR"]}, {"op": "uri", "match": "prefix", "value": "/login"}]},
                        "threshold": {"count": 10, "window": 60, "key": "ip"},
                        "action": {"type": "challenge", "provider": "hcaptcha"},
                    }
                ],
            }
        },
    }
    assert result["variables"] == {"app.example.com_WORKFLOWS_HAS_CHALLENGE": "yes"}


def test_the_artefact_is_byte_stable_across_runs():
    db, config = FakeDB(_attached(_definition(_rule()))), _config()
    first = canonical_json(compile_config(db, config, _Logger())["data"])
    second = canonical_json(compile_config(db, config, _Logger())["data"])
    assert first == second


def test_group_values_are_inlined_with_every_kind_present():
    rule = _rule(condition={"op": "group", "kind": "ip", "group_id": "office-ips"}, action={"type": "block"}, threshold=None)
    groups = {"office-ips": {"entries": [{"kind": "ip", "value": "203.0.113.0/24"}, {"kind": "ip", "value": "198.51.100.0/24"}]}}

    data = compile_config(FakeDB(_attached(_definition(rule)), groups), _config(), _Logger())["data"]

    # Entry order is preserved, and every supported kind key exists so the runtime never
    # branches on nil.
    assert data["groups"] == {"office-ips": {"ip": ["203.0.113.0/24", "198.51.100.0/24"], "country": [], "asn": []}}


def test_a_group_deleted_behind_a_stored_rule_aborts_instead_of_compiling_an_empty_list():
    """The whole point of fail-closed: an empty group would silently stop matching."""
    rule = _rule(condition={"op": "group", "kind": "ip", "group_id": "ghost"}, action={"type": "block"}, threshold=None)
    with pytest.raises(ValueError, match="does not exist"):
        compile_config(FakeDB(_attached(_definition(rule))), _config(), _Logger())


def test_a_challenge_without_its_provider_credentials_aborts():
    with pytest.raises(ValueError, match="ANTIBOT_HCAPTCHA_SITEKEY is not configured"):
        compile_config(FakeDB(_attached(_definition(_rule()))), _config(ANTIBOT_HCAPTCHA_SITEKEY=""), _Logger())


def test_provider_credentials_are_read_per_service_with_the_global_fallback():
    config = _config(ANTIBOT_HCAPTCHA_SITEKEY="", **{"app.example.com_ANTIBOT_HCAPTCHA_SITEKEY": "per-service"})
    result = compile_config(FakeDB(_attached(_definition(_rule()))), config, _Logger())
    # Presence is all that is checked — no secret ever reaches the artefact.
    assert "per-service" not in canonical_json(result["data"])


def test_disabled_rules_and_empty_workflows_are_absent():
    data = compile_config(FakeDB(_attached(_definition(_rule("on"), _rule("off", enabled=False)))), _config(), _Logger())["data"]
    assert [rule["id"] for rule in data["workflows"]["wf-7c3e"]["rules"]] == ["on"]

    empty = compile_config(FakeDB(_attached(_definition(_rule("off", enabled=False)))), _config(), _Logger())["data"]
    assert empty["services"] == {} and empty["workflows"] == {}


def test_a_workflow_attached_twice_is_compiled_once_and_listed_per_service():
    entry = {"id": "wf-7c3e", "name": "Login protection", "schema_version": 1, "definition": _definition(_rule())}
    attached = {"a.example.com": [entry], "b.example.com": [entry]}
    config = _config(SERVER_NAME="a.example.com b.example.com")

    data = compile_config(FakeDB(attached), config, _Logger())["data"]
    assert data["services"] == {"a.example.com": ["wf-7c3e"], "b.example.com": ["wf-7c3e"]}
    assert len(data["workflows"]) == 1


def test_the_challenge_flag_is_emitted_for_every_server():
    challenging = {"id": "wf-a", "name": "A", "schema_version": 1, "definition": _definition(_rule())}
    blocking = {"id": "wf-b", "name": "B", "schema_version": 1, "definition": _definition(_rule(action={"type": "block"}, threshold=None))}
    attached = {"a.example.com": [challenging], "b.example.com": [blocking]}
    config = _config(SERVER_NAME="a.example.com b.example.com c.example.com")

    variables = compile_config(FakeDB(attached), config, _Logger())["variables"]
    # A missing key would render as a Jinja Undefined in the ModSecurity template, so even
    # servers with no workflow at all get an explicit "no".
    assert variables == {
        "a.example.com_WORKFLOWS_HAS_CHALLENGE": "yes",
        "b.example.com_WORKFLOWS_HAS_CHALLENGE": "no",
        "c.example.com_WORKFLOWS_HAS_CHALLENGE": "no",
    }


def test_single_site_mode_emits_the_flag_unprefixed():
    config = _config(MULTISITE="no", SERVER_NAME="solo.example.com")
    variables = compile_config(FakeDB(_attached(_definition(_rule()), server="solo.example.com")), config, _Logger())["variables"]
    assert variables == {"WORKFLOWS_HAS_CHALLENGE": "yes"}


def test_an_unreadable_or_future_definition_aborts():
    broken = {"app.example.com": [{"id": "wf", "name": "Broken", "schema_version": 1, "definition": "{not json"}]}
    with pytest.raises(ValueError, match="unreadable definition"):
        compile_config(FakeDB(broken), _config(), _Logger())

    future = {"app.example.com": [{"id": "wf", "name": "Future", "schema_version": 2, "definition": _definition(_rule())}]}
    with pytest.raises(ValueError, match="unsupported schema version"):
        compile_config(FakeDB(future), _config(), _Logger())


def test_nothing_attached_still_produces_an_artefact():
    """Detaching the last workflow must clear the instances, not leave the old plan live."""
    result = compile_config(FakeDB({}), _config(), _Logger())
    assert result["data"]["services"] == {} and result["data"]["workflows"] == {}
    assert result["variables"] == {"app.example.com_WORKFLOWS_HAS_CHALLENGE": "no"}
