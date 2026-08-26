from typing import Any, Dict, Mapping, Sequence

from ports import HTTP_PORT_SETTING, http01_refusals, services_from_config  # type: ignore


def http01_refusals_for(db, config: Mapping[str, Any], server_names: Sequence[str]) -> Dict[str, str]:
    """``{service: why}`` for each named service the merged ``config`` would strand on ``http-01``.

    The thin, database-aware wrapper around the pure :func:`ports.http01_refusals`: it recovers the
    one value a snapshot cannot carry, slices the prefixed configuration a write path is ABOUT TO
    PERSIST into per-service views, and delegates the judgement. ``ports`` itself stays free of I/O,
    which is what lets the renderer and the report reuse it.

    Judged on the merged result, never on the payload: the challenge and the port can arrive in
    different requests, or one of the two can already be stored, and only the merged config says
    whether the combination is reachable.

    ``server_names`` is the set of services to judge, and the caller chooses it: a single-service
    write judges only the service being written, so a pre-existing violation on a sibling cannot
    block an unrelated save, while a fleet-wide write has to judge every service it can strand.
    """
    # A snapshot carries the NON-default settings, so a fleet that never moved off the shipped
    # HTTP_PORT has no global row at all. Recover the DECLARED default (`get_config` default-fills
    # from `bw_settings.default`), the same fallback the services listing applies for `link_port`
    # (`db_methods/services.py:73-76`).
    #
    # Injected into the configuration BEFORE it is sliced, so it reaches BOTH sides of the
    # comparison. Adding it to the globals alone -- which is what this did originally -- made every
    # service that overrides nothing read as moved off a list it was never given: `[]` against
    # `['8080']`, reported as "it listens on its own HTTP port(s) (none)". On a stock fleet that
    # refused turning Let's Encrypt on at all.
    #
    # Gated on the BASE key, not on the whole list being empty: a fleet that added a second port
    # without moving the first one has a row for `HTTP_PORT_1` and none for `HTTP_PORT`, so a
    # list-wide gate never fires on exactly the shape that needs it. And keyed on the key being
    # ABSENT, never on its value being empty: `HTTP_PORT=""` is a deliberate global with a row.
    # Insertion order does not matter either way -- `collect_ports` orders a list by SUFFIX.
    config = dict(config)
    if HTTP_PORT_SETTING not in config:
        declared = db.get_config(global_only=True, methods=False, filtered_settings=(HTTP_PORT_SETTING,))
        if HTTP_PORT_SETTING in declared:
            config[HTTP_PORT_SETTING] = declared[HTTP_PORT_SETTING]

    services = services_from_config(config, list(server_names), multisite=True)
    # Strip EVERY judged service's prefix, not just one: with several names the leftover keys of a
    # sibling would otherwise be read as globals. It cannot change the answer for a single-service
    # call -- `collect_ports` only ever matches `HTTP_PORT` and `HTTP_PORT_<n>` exactly, so a
    # prefixed key was never a candidate either way.
    prefixes = tuple(f"{name}_" for name in server_names)
    globals_only = {key: value for key, value in config.items() if not key.startswith(prefixes)}
    return http01_refusals(services, globals_only)
