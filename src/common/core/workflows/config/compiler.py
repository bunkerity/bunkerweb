#!/usr/bin/env python3
"""Compile the stored workflow definitions into the artefact the Lua runtime evaluates.

Runs once per config generation, through the generic ``extensions.config`` hook, after
resource groups, redirects and upstreams have been expanded and before the templates are
rendered. Produces two things:

* ``variables`` — ``<server>_WORKFLOWS_HAS_CHALLENGE``, so the Antibot templates render the
  challenge location for a service that has a challenge rule even when ``USE_ANTIBOT=no``;
* ``data`` — the artefact, written by the core to ``/var/cache/bunkerweb/workflows/config.json``
  and shipped to every instance by the existing cache-push pipeline.

**Fail-closed, unlike the redirect and upstream resolvers.** Those degrade to "render what
you can" because a dropped redirect is a broken link. A dropped security rule is an opening,
so anything unexpected raises: the push is abandoned and every instance keeps serving the
artefact it already has. Everything raised here is also refused at write time by
``db_methods/workflows.py``, so reaching one of these means the database changed underneath
a validated definition (a group deleted by a direct write, a provider setting cleared).
"""

from json import JSONDecodeError, loads
from typing import Any, Dict, List

from redirect_resolver import config_servers  # type: ignore
from workflow_schema import (  # type: ignore
    GROUP_KINDS,
    MAX_ACTIVE_RULES_PER_SERVICE,
    MAX_ARTEFACT_BYTES,
    MAX_PCRE_PER_SERVICE,
    MAX_PREDICATES_PER_SERVICE,
    SCHEMA_VERSION,
    canonical_json,
    collect_group_refs,
    rule_stats,
    validate_definition,
)

# What a service must already have configured for a challenge provider to render. The
# secrets themselves stay in the service settings and are never copied into the artefact;
# only their presence is checked.
PROVIDER_REQUIREMENTS = {
    "recaptcha": ("ANTIBOT_RECAPTCHA_SITEKEY", "ANTIBOT_RECAPTCHA_SECRET"),
    "hcaptcha": ("ANTIBOT_HCAPTCHA_SITEKEY", "ANTIBOT_HCAPTCHA_SECRET"),
    "turnstile": ("ANTIBOT_TURNSTILE_SITEKEY", "ANTIBOT_TURNSTILE_SECRET"),
    "mcaptcha": ("ANTIBOT_MCAPTCHA_SITEKEY", "ANTIBOT_MCAPTCHA_SECRET", "ANTIBOT_MCAPTCHA_URL"),
    "capjs": ("ANTIBOT_CAPJS_SITEKEY", "ANTIBOT_CAPJS_SECRET"),
}


def _group_index(db) -> Dict[str, Dict[str, List[str]]]:
    """Resource groups keyed by id, values bucketed by kind, entry order preserved."""
    index: Dict[str, Dict[str, List[str]]] = {}
    for group_id, group in (db.get_resource_groups() or {}).items():
        by_kind: Dict[str, List[str]] = {}
        for entry in group.get("entries") or []:
            by_kind.setdefault(entry["kind"], []).append(entry["value"])
        index[group_id] = by_kind
    return index


def _service_setting(config: Dict[str, Any], server: str, setting: str) -> str:
    """Per-service value with the global fallback multisite settings inherit."""
    value = config.get(f"{server}_{setting}")
    if value is None:
        value = config.get(setting)
    return str(value or "").strip()


def compile_config(db, config: Dict[str, Any], logger) -> Dict[str, Any]:
    attached = db.get_service_workflows() or {}
    index = _group_index(db)

    compiled: Dict[str, Dict[str, Any]] = {}
    services: Dict[str, List[str]] = {}
    used_groups: Dict[str, Dict[str, List[str]]] = {}
    challenged: set = set()

    for server, entries in sorted(attached.items()):
        totals = {"rules": 0, "predicates": 0, "pcre": 0}
        order: List[str] = []

        for entry in entries:
            workflow_id, name = entry["id"], entry["name"]
            if entry.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Workflow “{name}” uses unsupported schema version {entry.get('schema_version')!r}")
            try:
                raw = loads(entry["definition"])
            except JSONDecodeError as exc:
                raise ValueError(f"Workflow “{name}” holds an unreadable definition: {exc}") from exc

            definition, errors = validate_definition(raw, group_index=index)
            if definition is None:
                first = errors[0] if errors else {"path": "", "message": "invalid"}
                raise ValueError(f"Workflow “{name}” is invalid at {first['path'] or 'its root'}: {first['message']}")

            rules = [rule for rule in definition["rules"] if rule.get("enabled", True)]
            if not rules:
                # Nothing to evaluate: keep it out of the artefact entirely rather than
                # making the runtime iterate an empty workflow on every request.
                continue

            for key, value in rule_stats(definition).items():
                totals[key] += value

            for rule in rules:
                action = rule["action"]
                if action["type"] != "challenge":
                    continue
                challenged.add(server)
                for setting in PROVIDER_REQUIREMENTS.get(action["provider"], ()):
                    if not _service_setting(config, server, setting):
                        raise ValueError(f"Workflow “{name}” challenges {server} with {action['provider']}, but {setting} is not configured for that service")

            if workflow_id not in compiled:
                # Rules are compiled once and shared: a workflow attached to 500 services
                # costs one copy in the artefact and one prepared plan per worker.
                compiled[workflow_id] = {
                    "name": name,
                    "rules": [
                        {
                            "id": rule["id"],
                            # Precomputed so the request path never concatenates a counter key.
                            "counter": f"{workflow_id}/{rule['id']}",
                            "condition": rule["condition"],
                            "threshold": rule["threshold"],
                            "action": rule["action"],
                        }
                        for rule in rules
                    ],
                }
                for group_id, _kind in collect_group_refs(definition):
                    # Every kind key is present even when empty, so the runtime never has to
                    # branch on a missing table.
                    used_groups[group_id] = {kind: list(index.get(group_id, {}).get(kind, [])) for kind in GROUP_KINDS}

            order.append(workflow_id)

        if not order:
            continue
        if totals["rules"] > MAX_ACTIVE_RULES_PER_SERVICE:
            raise ValueError(f"Service {server} holds {totals['rules']} active workflow rules (maximum {MAX_ACTIVE_RULES_PER_SERVICE})")
        if totals["predicates"] > MAX_PREDICATES_PER_SERVICE:
            raise ValueError(f"Service {server} holds {totals['predicates']} workflow predicates (maximum {MAX_PREDICATES_PER_SERVICE})")
        if totals["pcre"] > MAX_PCRE_PER_SERVICE:
            raise ValueError(f"Service {server} holds {totals['pcre']} workflow regular expressions (maximum {MAX_PCRE_PER_SERVICE})")
        services[server] = order

    artefact = {"schema_version": SCHEMA_VERSION, "groups": used_groups, "services": services, "workflows": compiled}
    size = len(canonical_json(artefact).encode("utf-8"))
    if size > MAX_ARTEFACT_BYTES:
        raise ValueError(f"The compiled workflow artefact is {size} bytes (maximum {MAX_ARTEFACT_BYTES})")

    # Emitted for every server, not only the challenged ones: the ModSecurity template reads
    # ``all[server_name + "_WORKFLOWS_HAS_CHALLENGE"]`` and a missing key would render as a
    # Jinja Undefined instead of "no".
    multisite = str(config.get("MULTISITE", "no")).lower() == "yes"
    servers = config_servers(config)
    if multisite:
        variables = {f"{server}_WORKFLOWS_HAS_CHALLENGE": ("yes" if server in challenged else "no") for server in servers}
    else:
        variables = {"WORKFLOWS_HAS_CHALLENGE": "yes" if challenged else "no"}

    if services:
        logger.info(f"Compiled {len(compiled)} workflow(s) for {len(services)} service(s) ({size} bytes)")
    return {"variables": variables, "data": artefact}
