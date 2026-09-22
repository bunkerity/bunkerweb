"""Custom-config writes must be refused for a session without the `write` permission.

`/configs/*` gated its five write paths on `API_CLIENT.readonly` alone -- the DATABASE's
read-only flag -- so a user whose permissions are `{"read"}` (api/app/routers/auth.py:86-110)
could POST raw NGINX/ModSecurity snippets into a server block. The UI is the only enforcement
point here: it holds one process-wide bearer token, so the API sees the same caller whatever
the session is.

Same loader idiom as `test_service_mode_ui.py`: `app.dependencies` boots container-only state
at import, so the route module is executed against stubs, and `login_required` is baked in at
import time so the views are driven through `__wrapped__`. The permission itself is patched
where `is_readonly_request` reads it -- `app.utils.current_user` -- exactly as
`test_save_scope.py::_with_permissions` does.
"""

import importlib.util
import sys
from itertools import islice
from io import BytesIO
from json import dumps
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "configs.py"

SERVICE = "app.example.com"


@pytest.fixture
def configs_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = {}

    # `app.routes.utils` imports qrcode at module scope (routes/utils.py:10); it is an image-only
    # dependency, so stub it the way `test_service_mode_ui.py` does.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()

    module_name = "app.routes._configs_write_permission_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
        yield module


class _Data(dict):
    load_from_file = Mock()


@pytest.fixture
def route_app(configs_route, monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test

    # `handle_error` flashes and redirects; returning the message with a status instead makes the
    # refusal readable in `response.data` without parsing a flash out of the session.
    monkeypatch.setattr(configs_route, "handle_error", lambda message, *_args, **_kwargs: (message, 403))
    monkeypatch.setattr(configs_route, "verify_data_in_form", lambda **_kwargs: True)
    monkeypatch.setattr(configs_route, "wait_applying", Mock())
    monkeypatch.setattr(configs_route, "DATA", _Data(TO_FLASH=[]))
    # Run the submitted closure inline: without this an unfixed route would "pass" simply because
    # the write never left the executor stub.
    configs_route.CONFIG_TASKS_EXECUTOR.submit.side_effect = lambda function, *args: function(*args)

    configs_route.API_CLIENT.readonly = False
    configs_route.API_CLIENT.get_configs.return_value = [{"service": SERVICE, "type": "server_http", "name": "test", "method": "ui", "is_draft": False}]
    configs_route.API_CLIENT.get_config_item.return_value = {
        "service": SERVICE,
        "type": "server-http",
        "name": "test",
        "method": "ui",
        "template": "",
        "data": "x",
    }
    configs_route.BW_CONFIG.get_config.return_value = {"SERVER_NAME": SERVICE}

    for endpoint, view, rule in (
        ("configs_convert", configs_route.configs_convert, "/configs/convert"),
        ("configs_delete", configs_route.configs_delete, "/configs/delete"),
        ("configs_new", configs_route.configs_new, "/configs/new"),
        ("configs_edit", configs_route.configs_edit, "/configs/<string:service>/<string:config_type>/<string:name>"),
        ("configs_import", configs_route.configs_import, "/configs/import"),
    ):
        app.add_url_rule(rule, endpoint=endpoint, view_func=view.__wrapped__, methods=["POST"])
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
    app.add_url_rule("/configs", endpoint="configs.configs_page", view_func=lambda: "configs")
    app.add_url_rule("/configs/new", endpoint="configs.configs_new", view_func=lambda: "new")
    app.add_url_rule(
        "/configs/<string:service>/<string:config_type>/<string:name>",
        endpoint="configs.configs_edit",
        view_func=lambda service, config_type, name: "edit",
    )
    return app


def _read_only_user():
    """A logged-in session that holds `read` and not `write`, patched where the helper reads it."""
    return patch("app.utils.current_user", SimpleNamespace(list_permissions=["read"]))


IMPORT_PAYLOAD = dumps({"configs": [{"name": "imported", "type": "server-http", "service_id": SERVICE, "data": "# x", "is_draft": False}]})

# (route, form data, files) -- every write path `/configs` exposes.
WRITE_POSTS = (
    ("/configs/convert", {"configs": dumps([{"service": SERVICE, "type": "server-http", "name": "test"}]), "convert_to": "draft"}, None),
    ("/configs/delete", {"configs": dumps([{"service": SERVICE, "type": "server-http", "name": "test"}])}, None),
    ("/configs/new", {"service": SERVICE, "type": "SERVER_HTTP", "name": "evil", "value": "return 200 'pwned';"}, None),
    (f"/configs/{SERVICE}/server-http/test", {"service": SERVICE, "type": "SERVER_HTTP", "name": "test", "value": "return 200 'pwned';"}, None),
    ("/configs/import", {}, {"configs_file": (BytesIO(IMPORT_PAYLOAD.encode()), "export.json")}),
)


@pytest.mark.parametrize("route, form, files", WRITE_POSTS, ids=[post[0] for post in WRITE_POSTS])
def test_a_session_without_write_cannot_change_custom_configs(configs_route, route_app, route, form, files):
    payload = dict(form)
    if files:
        payload.update(files)

    with _read_only_user(), route_app.test_client() as client:
        response = client.post(route, data=payload, content_type="multipart/form-data" if files else None)

    # The write first: that is the hole, and an assertion on the message alone would report a
    # wording mismatch where the snippet actually reached the server block.
    assert not configs_route.API_CLIENT.create_config.called, f"{route} created a custom config"
    assert not configs_route.API_CLIENT.update_config.called, f"{route} updated a custom config"
    assert not configs_route.API_CLIENT.delete_configs.called, f"{route} deleted custom configs"
    assert b"permission" in response.data, f"{route} answered {response.data[:200]!r}"
    assert b"read-only" not in response.data, "the database is fine here -- one message for both causes misleads the operator"


def test_a_read_only_database_still_says_so(configs_route, route_app):
    """The permission refusal must not swallow the pre-existing one."""
    configs_route.API_CLIENT.readonly = True

    with _read_only_user(), route_app.test_client() as client:
        response = client.post("/configs/delete", data={"configs": dumps([{"service": SERVICE, "type": "server-http", "name": "test"}])})

    assert b"read-only" in response.data
    assert not configs_route.API_CLIENT.delete_configs.called


# --------------------------------------------------------------------------------------
# The shape, across every blueprint
# --------------------------------------------------------------------------------------
# F-01 was not one route's mistake, it was a pattern: ~40 write routes checked the DATABASE's
# read-only flag and called it authorization. The behavioural tests above cover `/configs`; this
# one covers the other twelve blueprints, which have no logged-in user in their harnesses and
# therefore stub `is_readonly_request` out. Without it, deleting the permission half from
# `bans`, `instances`, `pro`, `cache`, `jobs`, `web_cache`, `resource_groups` or any of the four
# `_readonly()` helpers leaves the whole UI suite green.
ROUTES_DIR = ROUTE_PATH.parent

# A `write` permission is not what these need, or not in this shape.
#   profile.py -- self-service: a read-only operator still changes their own password, TOTP,
#                 passkeys and sessions. `src/ui/main.py` carries the matching `/profile`
#                 exemption in the `is_readonly` context processor.
#   setup.py   -- the wizard serves an ANONYMOUS first install, where there is no session to hold
#                 a permission. It does gate the authenticated case, but as
#                 `if current_user.is_authenticated and is_readonly_request(...)`, which the
#                 bare-prefix match below deliberately does not accept. Pinned behaviourally by
#                 tests/unit/ui/test_setup_reserved_default_server.py instead.
PERMISSION_EXEMPT_MODULES = {"profile.py", "setup.py"}

# Prefixes, not substrings, and they must be the whole condition of an `if` at the gate's own
# indent. A bare `is_readonly_request(` substring is satisfied by a COMMENT, or by an assignment
# such as `is_readonly = is_readonly_request(API_CLIENT.readonly)` -- which is exactly the
# ineffective shape this lane had to fix on the settings pages, and three of those assignments
# still live ~15 lines below their gate.
PERMISSION_CHECKS = ("if is_readonly_request(", "if _user_readonly()", "if not current_user.admin")


def test_every_database_readonly_gate_has_a_permission_half():
    """`API_CLIENT.readonly` answers "can the database be written", never "may this user write".

    One process-wide bearer token reaches the API, so a gate that asks only the first question
    lets any logged-in session perform the action. Anything landing here is a new instance of
    F-01: add the second check, or add the module to `PERMISSION_EXEMPT_MODULES` with a reason.
    """
    missing = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        if path.name in PERMISSION_EXEMPT_MODULES:
            continue
        lines = path.read_text().splitlines()
        for index, line in enumerate(lines):
            if line.strip() != "if API_CLIENT.readonly:":
                continue
            indent = len(line) - len(line.lstrip())
            # Stop at the first line that dedents out of the gate's own block -- otherwise the
            # window reads into the next function and a stray mention there satisfies the check.
            window = []
            for candidate in islice(lines, index + 1, index + 13):
                if candidate.strip() and len(candidate) - len(candidate.lstrip()) < indent:
                    break
                window.append(candidate)
            prefixes = tuple(" " * indent + check for check in PERMISSION_CHECKS)
            if not any(candidate.startswith(prefixes) for candidate in window):
                missing.append(f"{path.name}:{index + 1}")

    assert not missing, "database-only readonly gates (see the docstring): " + ", ".join(missing)
