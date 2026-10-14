#!/usr/bin/env python3
"""What a reload answer means for the UI's NGINX failover banner, and how that state is stored.

The banner is a per-host state: `bw_metadata.failover_message` holds `{host: refusal message}` and
`failover` is true while it is not empty. Every process that reloads instances (push-configs, the
worker's cache push, the API's reload routes, the certbot jobs) classifies the answers here and
hands them to `Database.record_reload_outcome`, which applies them under the metadata row lock.

Stored format, chosen so that parsing never guesses: each block is `"<host> - <first line>"` and
every further line of that message is prefixed with two spaces. A block starts exactly at a line
that is not indented. Text that does not parse cleanly in this format -- rows written by 1.6.x or by
the old push-configs, which joined multi-line NGINX output unindented -- is carried verbatim as one
opaque entry under `LEGACY_HOST` instead of being split into guessed hosts.
"""

from re import compile as re_compile
from typing import Any, Dict, Mapping, Optional

# The two 503 answers of an instance whose configuration swap is still running (api.lua). They say
# nothing about the configuration, so they must neither raise nor clear the banner.
BUSY_REPLIES = ("a configuration swap is still in progress", "cannot take the swap lock")
# Pseudo-host of the opaque legacy entry. Parentheses can never appear in a hostname, so no real
# instance can collide with it; the banner reads "(earlier) - <the old text>".
LEGACY_HOST = "(earlier)"

_BLOCK = re_compile(r"(\S+) - (.*)")
_CONTINUATION = "  "


def normalize_host(host: Any) -> str:
    """Lower-case and whitespace-free, which is also how `urlsplit(...).hostname` reports it."""
    return "_".join(str(host).split()).lower()


def classify_reload_responses(responses: Optional[Mapping[str, Any]]) -> Dict[str, Optional[str]]:
    """`{host: None}` when the instance accepted the reload, `{host: message}` when it refused.

    Hosts that did not answer, and hosts that answered "busy", are left out: the banner only moves
    on an actual verdict.
    """
    results: Dict[str, Optional[str]] = {}
    for host, body in (responses or {}).items():
        if not isinstance(body, dict) or not body:
            continue
        message = str(body.get("msg") or "")
        if body.get("status") != "success" and message.startswith(BUSY_REPLIES):
            continue
        key = normalize_host(host)
        if key:
            results[key] = None if body.get("status") == "success" else (message or "reload refused")
    return results


def render_failover_message(entries: Mapping[str, str]) -> str:
    blocks = []
    for host in sorted(entries):
        first, *rest = entries[host].split("\n")
        blocks.append("\n".join([f"{host} - {first}", *(_CONTINUATION + line for line in rest)]))
    return "\n".join(blocks)


def parse_failover_message(text: str) -> Optional[Dict[str, str]]:
    """The stored text as `{host: message}`, or `None` when it is not cleanly in the stored format."""
    if not text.strip():
        return {}
    entries: Dict[str, str] = {}
    host: Optional[str] = None
    lines: list = []
    for line in text.split("\n"):
        if line.startswith(_CONTINUATION):
            if host is None:
                return None
            lines.append(line[len(_CONTINUATION) :])
            continue
        block = _BLOCK.fullmatch(line)
        if block is None or block.group(1) in entries or block.group(1) == host:
            return None
        if host is not None:
            entries[host] = "\n".join(lines)
        host, lines = block.group(1), [block.group(2)]
    if host is not None:
        entries[host] = "\n".join(lines)
    return entries


def record_reload_responses(db: Any, responses: Optional[Mapping[str, Any]], *, fleet: bool = False, logger: Any = None) -> None:
    """Classify a reload's answers and record them. Never raises: the caller's control flow is its own.

    `fleet` says the reload went to the whole fleet rather than one host; only then may the database
    treat "every known instance accepted" as the end of a legacy entry and forget instances that no
    longer exist.
    """
    try:
        results = classify_reload_responses(responses)
        if db is None or not results:
            return
        err = db.record_reload_outcome(results, fleet=fleet)
    except Exception as exc:
        err = str(exc)
    if err and logger is not None:
        if "read-only" in err:
            logger.debug(f"Not recording the failover state: {err}")
        else:
            logger.error(f"Failed to record the failover state: {err}")
