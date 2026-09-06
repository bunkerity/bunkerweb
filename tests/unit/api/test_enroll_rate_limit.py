"""``POST /instances/enroll`` must inherit the tight ``/auth`` limit, not the 100/min base one.

It is the only unauthenticated endpoint that hands out a credential on success. At the base
``API_RATE_LIMIT`` (100 requests/minute) a five-attempt lockout still leaves an attacker ~20
distinct hostnames per minute to probe; at ``API_RATE_LIMIT_AUTH`` (10/minute) it does not. The
limit is applied by ``_auth_default_limit``, which is a path allowlist -- adding a route to the
service without adding it there silently gives it the loose limit.

Executes the resolver out of the module rather than importing ``rate_limit`` (which pulls in
slowapi, fastapi and the API config at import time).
"""

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

RATE_LIMIT = Path(__file__).resolve().parents[3] / "src" / "api" / "app" / "rate_limit.py"


def _load_auth_default_limit(auth_limit):
    tree = ast.parse(RATE_LIMIT.read_text(encoding="utf-8"), filename=str(RATE_LIMIT))
    wanted = {"_auth_default_limit", "_normalize_method", "_path_variants"}
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in wanted)
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", "") == "_AUTH_DEFAULT_PATHS" for tgt in node.targets))
    ]
    assert len(nodes) == len(wanted) + 1, "rate_limit.py no longer exposes the pieces this test executes"
    namespace = {
        "Optional": Optional,
        "List": list,
        "_auth_limit": auth_limit,
        # _path_variants only consults the root path, which is empty in every default deployment.
        "api_config": SimpleNamespace(API_ROOT_PATH=""),
    }
    exec(compile(ast.Module(nodes, type_ignores=[]), str(RATE_LIMIT), "exec"), namespace)
    return namespace["_auth_default_limit"]


def test_enroll_gets_the_auth_limit():
    resolve = _load_auth_default_limit("10/minute")
    assert resolve("POST", "/instances/enroll") == "10/minute"
    assert resolve("POST", "/instances/enroll/") == "10/minute"
    assert resolve("POST", "/auth") == "10/minute"


def test_the_admin_enrollment_routes_keep_the_base_limit():
    """Those are guarded; throttling an operator issuing codes at 10/min is pointless."""
    resolve = _load_auth_default_limit("10/minute")
    assert resolve("POST", "/instances/bw-1/enroll") is None
    assert resolve("POST", "/instances/bw-1/rotate") is None
    assert resolve("GET", "/instances/enroll") is None


def test_disabling_the_auth_limit_disables_it_here_too():
    assert _load_auth_default_limit(None)("POST", "/instances/enroll") is None
