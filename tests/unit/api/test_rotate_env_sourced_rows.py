"""Rotation is refused on env-sourced rows — driven through a REAL projection.

``POST /instances/{hostname}/rotate`` used to gate on the derived ``enrollment_state`` string
alone. That string says "a credential exists", not "the control plane owns this row", and an
env-sourced row legitimately holds one: ``save_config.py`` stores
``BUNKERWEB_INSTANCE_API_TOKEN_n`` on its ``manual`` rows and the autoconf reconcile encrypts
``env["API_TOKEN"]`` on its own. Both therefore read ``"enrolled"``.

Rotating one is not recoverable from the UI: the instance persists the minted credential and stops
accepting the environment token, the next reconcile puts the environment token back in the
database, and ``/enroll``, ``/revoke`` and ``DELETE`` all refuse the row by method. Someone has to
delete a file on the box.

Every other rotate test hand-builds the instance dict, which is exactly why this was invisible —
so this file builds the row with the real ``Database`` and reads it back through the real
projection.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
ROUTER_SOURCE = ROOT / "src" / "api" / "app" / "routers" / "instances.py"

# The real tuple, not a lookalike: the rotate guard imports it from here, and lane L-A3 is
# about to widen it. A hard-coded copy in the stub would keep passing after that.
from db_methods.instances import ENROLLABLE_METHODS  # type: ignore  # noqa: E402


class _Router:
    def __init__(self, **_kwargs):
        pass

    def _passthrough(self, *_args, **_kwargs):
        return lambda function: function

    get = post = put = patch = delete = _passthrough


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_inst": ModuleType("bw_inst"),
        "bw_inst.routers": ModuleType("bw_inst.routers"),
        "bw_inst.auth": ModuleType("bw_inst.auth"),
        "bw_inst.auth.guard": ModuleType("bw_inst.auth.guard"),
        "bw_inst.deps": ModuleType("bw_inst.deps"),
        "bw_inst.schemas": ModuleType("bw_inst.schemas"),
        "bw_inst.config": ModuleType("bw_inst.config"),
        "bw_inst.utils": ModuleType("bw_inst.utils"),
        "common_utils": ModuleType("common_utils"),
        "db_methods": ModuleType("db_methods"),
        "db_methods.instances": ModuleType("db_methods.instances"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    for pkg in ("bw_inst", "bw_inst.routers", "bw_inst.auth", "db_methods"):
        names[pkg].__path__ = []
    names["bw_inst.auth.guard"].guard = object()
    names["bw_inst.deps"].get_instances_api_caller = Mock()
    names["bw_inst.deps"].get_api_for_hostname = Mock()
    for schema in (
        "BulkUpdateInstancesRequest",
        "InstanceCreateRequest",
        "InstanceEnrollRedeemRequest",
        "InstanceEnrollRequest",
        "InstancesDeleteRequest",
        "InstanceStatusRequest",
        "InstanceUpdateRequest",
    ):
        setattr(names["bw_inst.schemas"], schema, object)
    names["bw_inst.config"].api_config = SimpleNamespace()
    names["bw_inst.utils"].get_db = Mock()
    names["bw_inst.utils"].LOGGER = Mock()
    names["common_utils"].parse_host = Mock()
    names["API"] = ModuleType("API")
    names["API"].API = Mock()
    names["db_methods.instances"].ENROLLABLE_METHODS = ENROLLABLE_METHODS
    names["db_methods.instances"].ENROLLMENT_REJECTED = "invalid or expired enrollment code"
    with patch.dict(sys.modules, names):
        spec = importlib.util.spec_from_file_location("bw_inst.routers.instances", ROUTER_SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()

_TEST_KEY_ID = "test-key-1"


@pytest.fixture
def real_db(db, monkeypatch):
    """The real ``Database``, wired into the router, with a keyring so credentials can be stored."""
    import base64
    import json

    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_KEYS", json.dumps({_TEST_KEY_ID: base64.b64encode(b"\x00" * 32).decode()}))
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", _TEST_KEY_ID)
    db.initialize_db("1.7.0", "Docker")
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    return db


# Derived, never hard-coded: lane L-A3 widens `ENROLLABLE_METHODS` to include "manual", and a
# literal list here would then be asserting the opposite of the shipped rule while still passing.
ENV_SOURCED_METHODS = tuple(m for m in ("manual", "autoconf", "scheduler") if m not in ENROLLABLE_METHODS)


@pytest.mark.parametrize("method", ENV_SOURCED_METHODS)
def test_an_env_sourced_row_with_a_credential_cannot_be_rotated(real_db, method):
    assert real_db.add_instance("bw-env", 5000, "bwapi", method) == ""
    assert real_db.set_instance_credential("bw-env", "the-environment-token") == ""

    instance = real_db.get_instance("bw-env")
    # The derived string really does say "enrolled" -- that is the trap, and the reason the gate
    # cannot be the string. Pinning it here so a future change to the derivation is not silently
    # allowed to be the fix.
    assert instance["method"] == method
    assert instance["enrollment_state"] == "enrolled"

    resp = ROUTER.rotate_credential("bw-env", Mock())
    assert resp.status_code == 409
    assert "sourced from its environment" in resp.content["message"]


def test_a_control_plane_row_is_still_rotatable(real_db):
    """The guard must refuse the method, not the credential: a `ui` row still gets past it."""
    assert real_db.add_instance("bw-ui", 5000, "bwapi", "ui") == ""
    assert real_db.set_instance_credential("bw-ui", "minted") == ""
    assert real_db.get_instance("bw-ui")["enrollment_state"] == "enrolled"

    api = Mock()
    api.request.return_value = (True, "", 200, {})
    resp = ROUTER.rotate_credential("bw-ui", api)
    assert resp.status_code == 200


def test_an_env_sourced_row_without_a_credential_is_refused_by_the_method_too(real_db):
    """`none` would have 409'd on the state check alone; the method check must come first, so the
    message names the real reason."""
    assert real_db.add_instance("bw-plain", 5000, "bwapi", ENV_SOURCED_METHODS[0]) == ""
    resp = ROUTER.rotate_credential("bw-plain", Mock())
    assert resp.status_code == 409
    assert "sourced from its environment" in resp.content["message"]


def test_the_guard_follows_the_shared_tuple_not_a_local_copy(real_db, monkeypatch):
    """The router imports `ENROLLABLE_METHODS` from the DB layer rather than reusing its own
    `UI_API_METHODS` (the *delete* predicate, equal today by coincidence). Widening enrollment --
    which lane L-A3 does -- must reach this guard without anyone editing it. Reproducing that
    widening on the router's binding is the whole test: with a local copy it stays 409."""
    method = ENV_SOURCED_METHODS[0]
    assert real_db.add_instance("bw-widened", 5000, "bwapi", method) == ""
    assert real_db.set_instance_credential("bw-widened", "minted") == ""

    monkeypatch.setattr(ROUTER, "ENROLLABLE_METHODS", ENROLLABLE_METHODS + (method,))
    api = Mock()
    api.request.return_value = (True, "", 200, {})
    assert ROUTER.rotate_credential("bw-widened", api).status_code == 200
