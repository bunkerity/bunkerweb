"""Confirm accepted reloads through health without sending another reload."""

from time import monotonic, sleep
from typing import Any, Dict, List, Tuple, Union
from urllib.parse import urlsplit

# Scheduler waits out slow worker initialization (30–50s); a rejected marker may linger
# for five minutes, so the wait never exceeds that bound.
RELOAD_CONFIRM_MIN_WAIT = 60
RELOAD_CONFIRM_MAX_WAIT = 300
RELOAD_CONFIRM_POLL = 2
# Extra confirmation budget for synchronous UI/API requests, shared by all instances.
RELOAD_CONFIRM_HTTP_WAIT = 5


def wait_for_reload(apis: List[Any], responses: Dict[str, Any], timeout: Union[int, float]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return (pending, failed), keyed by URL hostname, for HTTP-200 unconfirmed reloads.

    One deadline covers all instances, sleeps and health requests. Transport failures leave
    readiness unknown; an explicit instance error fails confirmation. Confirmed/legacy replies
    need no probe. The caller retains pending responses if it needs to check again next cycle.
    """
    pending = {
        hostname.strip("[]").lower(): "unreachable"
        for hostname, response in responses.items()
        if isinstance(response, dict) and response.get("status") == "success" and response.get("confirmed") is False
    }
    if not pending:
        return {}, {}

    targets = {urlsplit(api.endpoint).hostname: api for api in apis}
    failed = {}
    deadline = monotonic() + timeout
    while pending:
        for hostname in list(pending):
            remaining = deadline - monotonic()
            if remaining <= 0:
                return pending, failed
            api = targets.get(hostname)
            if api is None:
                continue
            try:
                sent, _, status, resp = api.request("GET", "health", timeout=(min(5, remaining / 2), min(10, remaining / 2)))
                if sent and isinstance(resp, dict):
                    state = str(resp.get("msg") or "unknown")
                    if status != 200 or resp.get("status") == "error":
                        failed[hostname] = state
                        del pending[hostname]
                    elif state == "ok":
                        del pending[hostname]
                    else:
                        pending[hostname] = state
                else:
                    pending[hostname] = "unreachable"
            except Exception:
                pending[hostname] = "unreachable"
        if pending:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            sleep(min(RELOAD_CONFIRM_POLL, remaining))
    return pending, failed
