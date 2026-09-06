"""FastAPI instances router — the enrollment endpoints.

Follows the module-loader + stubbed ``sys.modules`` pattern of ``test_plugins_toggle.py``:
router functions are called directly against a ``Mock`` db.

What matters here and nowhere else:

* ``POST /instances/enroll`` carries **no** ``Depends(guard)``. It is the only route in the
  service reachable before a credential exists, so this file pins both that it is unguarded and
  that every rejection answers the same opaque 401.
* the rotation writes the database **last**, and rolls the instance back when that write fails.
  Getting the order wrong locks the control plane out of a healthy instance, and no test on the
  happy path would notice.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
ROUTER_SOURCE = ROOT / "src" / "api" / "app" / "routers" / "instances.py"

ENROLLMENT_REJECTED = "invalid or expired enrollment code"

# The real tuple, not a lookalike: the rotate guard imports it from here, and lane L-A3 is
# about to widen it. A hard-coded copy in the stub would keep passing after that.
from db_methods.instances import ENROLLABLE_METHODS  # type: ignore  # noqa: E402


class _Router:
    def __init__(self, **_kwargs):
        pass

    def _passthrough(self, *_args, **_kwargs):
        return lambda function: function

    get = _passthrough
    put = _passthrough
    post = _passthrough
    patch = _passthrough
    delete = _passthrough


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
    names["db_methods.instances"].ENROLLMENT_REJECTED = ENROLLMENT_REJECTED
    with patch.dict(sys.modules, names):
        spec = importlib.util.spec_from_file_location("bw_inst.routers.instances", ROUTER_SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


class _Redeem:
    def __init__(self, hostname, code):
        self.hostname = hostname
        self.code = code


class _Issue:
    def __init__(self, ttl_seconds=None):
        self.ttl_seconds = ttl_seconds


@pytest.fixture
def rollback_client(monkeypatch):
    """Capture the client the rollback builds and what it sends.

    Returns ``(built_with, sent)``: the instance dicts ``API.from_instance`` was called with, and
    the payloads that client actually put on the wire.
    """
    built_with, sent = [], []

    class _RollbackAPI:
        @staticmethod
        def from_instance(instance, **_kwargs):
            built_with.append(instance)

            class _Client:
                @staticmethod
                def request(_method, _url, data=None, **_kw):
                    sent.append(data)
                    return True, "", 200, {}

            return _Client()

    monkeypatch.setattr(ROUTER, "API", _RollbackAPI)
    return built_with, sent


class TestSelfEnrollIsUnguarded:
    def test_the_redeem_route_declares_no_guard(self):
        """The one route without Depends(guard). If this ever gains one, a booting instance can
        never enroll -- it has nothing to authenticate with yet."""
        source = ROUTER_SOURCE.read_text(encoding="utf-8")
        start = source.index('@router.post("/enroll")')
        decorator = source[start : source.index("def redeem_enrollment")]  # noqa: E203
        assert "guard" not in decorator
        # Every sibling enrollment route DOES carry it.
        for route in ('@router.post("/{hostname}/enroll"', '@router.post("/{hostname}/rotate"', '@router.post("/{hostname}/revoke"'):
            start = source.index(route)
            end = source.index(")\n", start) + 1
            assert "Depends(guard)" in source[start:end]


class TestRedeem:
    def test_success_returns_the_credential_once(self, db):
        db.redeem_enrollment_code.return_value = ("the-credential", "")
        resp = ROUTER.redeem_enrollment(_Redeem("bw-1", "code"))
        assert resp.status_code == 200
        assert resp.content["credential"] == "the-credential"
        db.redeem_enrollment_code.assert_called_once_with("bw-1", "code")

    def test_rejection_is_401_and_opaque(self, db):
        db.redeem_enrollment_code.return_value = (None, ENROLLMENT_REJECTED)
        resp = ROUTER.redeem_enrollment(_Redeem("bw-1", "wrong"))
        assert resp.status_code == 401
        assert resp.content["message"] == ENROLLMENT_REJECTED

    def test_operational_failure_is_503_not_401(self, db):
        """A missing keyring is an operator problem, not a wrong code; answering 401 would send
        them hunting for a bad code that does not exist."""
        db.redeem_enrollment_code.return_value = (None, "No certificate encryption keyring is configured")
        resp = ROUTER.redeem_enrollment(_Redeem("bw-1", "code"))
        assert resp.status_code == 503


class TestIssue:
    def test_success(self, db):
        db.issue_enrollment_code.return_value = ("the-code", "")
        resp = ROUTER.issue_enrollment("bw-1", _Issue(120))
        assert resp.status_code == 200
        assert resp.content["code"] == "the-code"
        db.issue_enrollment_code.assert_called_once_with("bw-1", 120)

    def test_no_body_means_default_ttl(self, db):
        db.issue_enrollment_code.return_value = ("the-code", "")
        ROUTER.issue_enrollment("bw-1", None)
        db.issue_enrollment_code.assert_called_once_with("bw-1", None)

    @pytest.mark.parametrize(
        ("err", "expected"),
        (
            ("Instance bw-1 does not exist", 404),
            ("The database is read-only, the changes will not be saved", 400),
            ("Instance bw-1 is sourced from its environment (method: autoconf)", 409),
            ("boom", 500),
        ),
    )
    def test_error_mapping(self, db, err, expected):
        db.issue_enrollment_code.return_value = (None, err)
        assert ROUTER.issue_enrollment("bw-1", None).status_code == expected


class TestRevoke:
    def test_success(self, db):
        db.get_instance.return_value = {"hostname": "bw-1"}
        db.revoke_instance_enrollment.return_value = ""
        resp = ROUTER.revoke_enrollment("bw-1")
        assert resp.status_code == 200
        assert resp.content["enrollment_state"] == "revoked"

    def test_unknown_instance(self, db):
        db.get_instance.return_value = {}
        assert ROUTER.revoke_enrollment("bw-1").status_code == 404


class TestRotate:
    def _enrolled(self):
        # `method` matters: rotation is refused on env-sourced rows, which can hold a credential of
        # their own and therefore also read "enrolled". See `test_rotate_env_sourced_rows.py`, which
        # drives that case through a real projection instead of a dict.
        return {"hostname": "bw-1", "method": "ui", "enrollment_state": "enrolled", "credential": "old-credential"}

    def test_instance_is_told_before_the_database(self, db):
        """The order is the whole safety property: the instance confirms, then we persist."""
        order = []
        db.get_instance.return_value = self._enrolled()
        api = Mock()
        api.request.side_effect = lambda *a, **k: (order.append("instance"), (True, "", 200, {}))[1]
        db.set_instance_credential.side_effect = lambda *a, **k: (order.append("db"), "")[1]

        resp = ROUTER.rotate_credential("bw-1", api)
        assert resp.status_code == 200
        assert order == ["instance", "db"]
        # The credential the instance was handed is the one persisted.
        assert api.request.call_args.kwargs["data"]["credential"] == db.set_instance_credential.call_args[0][1]

    def test_unreachable_instance_fails_and_keeps_the_old_credential(self, db, rollback_client):
        db.get_instance.return_value = self._enrolled()
        api = Mock()
        api.request.return_value = (False, "connection refused", None, None)

        resp = ROUTER.rotate_credential("bw-1", api)
        assert resp.status_code == 502
        db.set_instance_credential.assert_not_called()

    @pytest.mark.parametrize(
        ("err", "expected"),
        (("Instance bw-1 is sourced from its environment (method: autoconf)", 409), ("boom", 500)),
    )
    def test_revoke_error_mapping(self, db, err, expected):
        db.get_instance.return_value = {"hostname": "bw-1"}
        db.revoke_instance_enrollment.return_value = err
        assert ROUTER.revoke_enrollment("bw-1").status_code == expected

    def test_a_refusal_fails_without_rolling_anything_back(self, db, rollback_client):
        """`API.request()` returns sent=True only once it has an answer, so a non-200 means the
        instance answered and never renamed its credential file: nothing was written, nothing to
        undo. Rolling back here dialled the instance with a credential it correctly refuses and
        logged a CRITICAL telling the operator to re-enroll — on the ordinary failure."""
        db.get_instance.return_value = self._enrolled()
        api = Mock()
        api.request.return_value = (True, "", 500, {})
        assert ROUTER.rotate_credential("bw-1", api).status_code == 502
        db.set_instance_credential.assert_not_called()
        _, sent = rollback_client
        assert sent == [], "a refusal must not trigger a rollback"

    def test_database_failure_rolls_the_instance_back_with_the_new_credential(self, db, rollback_client):
        """Without the rollback the instance holds a credential the control plane never stored,
        and the control plane can no longer reach it at all.

        The credential the ROLLBACK authenticates with is the point: the instance has already
        committed the new one, so a rollback sent over the old one is refused and the recovery
        never happens. Asserting only ``call_count == 2`` would pass against that bug.
        """
        db.get_instance.return_value = self._enrolled()
        db.set_instance_credential.return_value = "database is locked"
        api = Mock()
        api.request.return_value = (True, "", 200, {})

        resp = ROUTER.rotate_credential("bw-1", api)
        assert resp.status_code == 500
        # Phase 1 went through the dependency client; the rollback did not.
        assert api.request.call_count == 1
        built_with, sent = rollback_client
        assert len(sent) == 1
        assert sent[0]["credential"] == "old-credential", "the rollback must restore the OLD credential"
        assert built_with[0]["credential"] == api.request.call_args.kwargs["data"]["credential"], (
            "the rollback client must authenticate with the NEW credential -- the instance has already " "stopped accepting the old one"
        )

    def test_a_lost_answer_does_trigger_a_rollback(self, db, rollback_client):
        """A timeout is not proof the instance did nothing. It may have committed and lost the
        reply, which is the one way to lock the control plane out for good. This is the only
        failure path where the rollback is warranted."""
        db.get_instance.return_value = self._enrolled()
        api = Mock()
        api.request.return_value = (False, "read timed out", None, None)

        assert ROUTER.rotate_credential("bw-1", api).status_code == 502
        db.set_instance_credential.assert_not_called()
        _, sent = rollback_client
        assert len(sent) == 1 and sent[0]["credential"] == "old-credential"

    def test_a_rollback_that_raises_does_not_replace_the_real_error(self, db, monkeypatch):
        """The rollback runs inside a failure path; letting it raise would swap a 500 that names
        the database problem for an opaque unhandled exception."""

        class _Exploding:
            @staticmethod
            def from_instance(_instance, **_kwargs):
                raise ValueError("Invalid API endpoint")

        monkeypatch.setattr(ROUTER, "API", _Exploding)
        db.get_instance.return_value = self._enrolled()
        db.set_instance_credential.return_value = "database is locked"
        api = Mock()
        api.request.return_value = (True, "", 200, {})

        resp = ROUTER.rotate_credential("bw-1", api)
        assert resp.status_code == 500
        assert resp.content["message"] == "database is locked"

    def test_unenrolled_instance_is_409(self, db):
        db.get_instance.return_value = {"hostname": "bw-1", "method": "ui", "enrollment_state": "none"}
        assert ROUTER.rotate_credential("bw-1", Mock()).status_code == 409

    def test_unknown_instance_is_404(self, db):
        db.get_instance.return_value = {}
        assert ROUTER.rotate_credential("bw-1", Mock()).status_code == 404
