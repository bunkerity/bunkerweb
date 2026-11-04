"""`POST /services/{id}/convert` must resolve to `service_convert`, not to `service_create`.

The resolver matched the literal path `/services/convert`, which the API does not serve: the
route carries the service id (`src/api/app/routers/services.py`, `@router.post("/{service}/convert")`).
A real convert request fell through to the verb fallback and asked for `service_create` instead —
so a user granted `service_convert` was refused, and one granted `service_create` could draft and
undraft every service without ever holding the permission named for it.

Same shape as `test_global_settings_acl.py`: parse `biscuit.py` and exec just the two functions
under test, so no auth stack and no SQLAlchemy import are needed. Port of dev `71f655084`.
"""

import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
BISCUIT = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"


def _load(*names):
    tree = ast.parse(BISCUIT.read_text(encoding="utf-8"), filename=str(BISCUIT))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in names)
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == "PERM_VERB_BY_METHOD" for tgt in node.targets))
    ]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(BISCUIT), "exec"), namespace)
    return namespace


NS = _load("_resolve_services", "_extract_resource_id")
resolve_services = NS["_resolve_services"]
extract_resource_id = NS["_extract_resource_id"]


class TestConvertPermission:
    def test_the_served_route_asks_for_service_convert(self):
        assert resolve_services("/services/www.example.com/convert", "POST") == ("services", "service_convert")

    def test_it_is_not_the_create_permission(self):
        """The defect: a convert grant was refused and a create grant was enough to convert."""
        assert resolve_services("/services/www.example.com/convert", "POST")[1] != "service_create"

    def test_plain_create_still_resolves_to_create(self):
        assert resolve_services("/services", "POST") == ("services", "service_create")

    def test_convert_is_a_post_only_action(self):
        assert resolve_services("/services/www.example.com/convert", "GET")[1] != "service_convert"

    def test_export_is_untouched(self):
        assert resolve_services("/services/export", "GET") == ("services", "service_export")


class TestRedirectCandidates:
    """`GET /services/redirect-candidates` is a fleet-wide read, and it resolves like one.

    It lands on `service_read` through the two-segment branch, and -- unlike `/services/export` and
    `/services/{id}/convert` -- it is deliberately NOT added to `_extract_resource_id`'s skip set.
    The literal path segment therefore becomes the resource id, so a token scoped to one service is
    refused. That is the wanted outcome: the endpoint answers for EVERY service, and skipping the
    id would let a single-service grant read the whole fleet's names back.
    """

    def test_it_asks_for_service_read(self):
        assert resolve_services("/services/redirect-candidates", "GET") == ("services", "service_read")

    def test_a_service_scoped_grant_does_not_reach_it(self):
        assert extract_resource_id("/services/redirect-candidates", "services") == "redirect-candidates"

    def test_it_is_a_read_only_route(self):
        assert resolve_services("/services/redirect-candidates", "POST")[1] != "service_read"


class TestResourceId:
    """The `>= 2` -> `== 2` tightening ported alongside the fix above.

    It changes nothing for any route the API serves — for `/services/{id}/convert`, `parts[1]` is
    the id, never the literal "convert", so the old form already returned it. What it removes is a
    latent trap: a service literally named "convert" or "export" would have had its id swallowed by
    the action-route skip on any deeper path. Pinned so the intent survives, not because a served
    endpoint changed.
    """

    def test_the_converted_service_is_the_resource(self):
        """The permission is per-service, so the id has to survive the action segment."""
        assert extract_resource_id("/services/www.example.com/convert", "services") == "www.example.com"

    def test_the_action_only_routes_carry_no_id(self):
        assert extract_resource_id("/services/export", "services") is None

    def test_a_service_named_after_an_action_keeps_its_id_on_a_deeper_path(self):
        assert extract_resource_id("/services/convert/settings", "services") == "convert"
