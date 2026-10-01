"""Where a session may go before its second factor is proven, and what a read-only role may reach.

N-B1  A reader with TOTP enabled could not finish logging in: POST /totp is a `write` for the
      Biscuit check, and the reader allowlist in `app/models/biscuit.py` covered /profile* and
      /set_language, not /totp. The security-key ceremony on /totp (two more POSTs) was refused
      the same way. Only "Back to Login" escaped.
B3    The MFA gate in `main.py` let a pending session reach `totp.totp_page` and `*/login` only, so
      the language selector on /totp (`POST /set_language`), the security-key ceremony and
      `GET /logout` were all redirected back to /totp.

The Biscuit part runs the shipped middleware with a real token and a real authorizer. `main.py`
cannot be imported in the unit venv, so the gate's allowlist is spliced out of its source, as
`test_session_plumbing.py` does, and checked against the routes that really exist.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from biscuit_auth import KeyPair
from flask import Flask

from test_session_plumbing import MAIN, _shipped, _tree

UI = Path(__file__).resolve().parents[3] / "src" / "ui"
ROUTES = UI / "app" / "routes"

# Every request the /totp page itself makes, plus the way out.
TOTP_PAGE_REQUESTS = (
    ("POST", "/totp"),
    ("POST", "/totp/webauthn/options"),
    ("POST", "/totp/webauthn/verify"),
)


@pytest.fixture(scope="module")
def biscuit_module():
    logout = ModuleType("app.routes.logout")
    logout.logout_page = lambda: "logged out"
    utils = ModuleType("app.utils")
    utils.BISCUIT_PRIVATE_KEY_FILE = Path("/nonexistent/biscuit.key")
    utils.is_static_path = lambda path, *extra: path.startswith(("/css/", "/js/", *extra))
    common_utils = ModuleType("common_utils")
    common_utils.get_version = lambda: "1.7.0"

    with patch.dict(sys.modules, {"app.routes.logout": logout, "app.utils": utils, "common_utils": common_utils}):
        spec = importlib.util.spec_from_file_location("app.models._biscuit_mfa_test", UI / "app" / "models" / "biscuit.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    # The 403 page is a template this app does not have; the verdict is all that matters here.
    module.render_error_page = lambda code, message=None: (message or "", code)
    return module


@pytest.fixture(scope="module")
def keypair():
    return KeyPair()


@pytest.fixture
def app(biscuit_module, keypair, tmp_path):
    public_key = tmp_path / "biscuit.pub"
    public_key.write_text(str(keypair.public_key))

    application = Flask("bw_ui_mfa_pending_test")
    application.secret_key = "test"
    application.config.update(BISCUIT_PUBLIC_KEY_PATH=str(public_key), CHECK_PRIVATE_IP=False)
    biscuit_module.BiscuitMiddleware(application)

    for method, rule in TOTP_PAGE_REQUESTS + (("POST", "/set_language"), ("POST", "/home"), ("POST", "/totp-evil")):
        application.add_url_rule(rule, endpoint=f"{method}{rule}", view_func=lambda: "reached", methods=[method])
    return application


def _as(app, biscuit_module, keypair, role):
    """A client whose session holds a real token for `role`, minted the way login.py mints it."""
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        token = biscuit_module.BiscuitTokenFactory(keypair.private_key).create_token_for_role(role, "someone").to_base64()
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["biscuit_token"] = token
    return client


@pytest.mark.parametrize("method,rule", TOTP_PAGE_REQUESTS)
def test_a_reader_can_prove_its_second_factor(app, biscuit_module, keypair, method, rule):
    response = _as(app, biscuit_module, keypair, "reader").open(rule, method=method)

    assert response.status_code == 200, f"{method} {rule} refused to a reader: {response.get_data(as_text=True)!r}"


@pytest.mark.parametrize("rule", ["/home", "/totp-evil"])
def test_a_reader_still_cannot_write_anywhere_else(app, biscuit_module, keypair, rule):
    """The allowlist is /totp and its own sub-paths, not every path that happens to start with it."""
    response = _as(app, biscuit_module, keypair, "reader").post(rule)

    assert response.status_code == 403


def test_a_writer_is_unaffected(app, biscuit_module, keypair):
    assert _as(app, biscuit_module, keypair, "writer").post("/home").status_code == 200


# ------------------------------------------------------------------------------ the MFA gate


def _gate_allowlist():
    return _shipped(MAIN, ("MFA_PENDING_ENDPOINTS",), {})["MFA_PENDING_ENDPOINTS"]


def _route_endpoints(path: Path, blueprint: str):
    """`<blueprint>.<view>` for every view `path` registers on its blueprint."""
    endpoints = set()
    for node in _tree(path).body:
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and ast.unparse(decorator.func) == f"{blueprint}.route":
                    endpoints.add(f"{blueprint}.{node.name}")
    return endpoints


def test_a_pending_session_reaches_everything_the_totp_page_needs():
    allowed = _gate_allowlist()

    # The code form and the security-key ceremony: every view of the totp blueprint.
    assert _route_endpoints(ROUTES / "totp.py", "totp") <= allowed
    # The language selector in the /totp top bar, and the way out.
    assert {"set_language", "logout.logout_page"} <= allowed


def test_the_gate_lets_nothing_else_through():
    """ "Exempt what the /totp page needs, nothing more": no profile, no home, no API proxy."""
    assert _gate_allowlist() == _route_endpoints(ROUTES / "totp.py", "totp") | {"set_language", "logout.logout_page"}


def test_every_allowlisted_endpoint_exists():
    main_views = {
        node.name
        for node in _tree(MAIN).body
        if isinstance(node, ast.FunctionDef) and any(isinstance(d, ast.Call) and ast.unparse(d.func) == "app.route" for d in node.decorator_list)
    }
    known = _route_endpoints(ROUTES / "totp.py", "totp") | _route_endpoints(ROUTES / "logout.py", "logout") | main_views

    assert _gate_allowlist() <= known


def test_the_gate_reads_the_allowlist():
    source = MAIN.read_text(encoding="utf-8")

    assert "request.endpoint not in MFA_PENDING_ENDPOINTS" in source
    assert 'request.endpoint != "totp.totp_page"' not in source
