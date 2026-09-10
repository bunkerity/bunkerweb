"""`SERVICE_MODE` gets an explicit, validated write path -- and a read-only audit that finds it.

Two endpoints, one rule. `POST /services/{id}/convert?mode=redirect_only` is the only code path in
the product that declares a service `redirect_only` after judging whether the declaration holds up;
`GET /services/redirect-candidates` answers the same question for every standard service without
writing anything. Both run the SHARED classifier (`src/common/utils/service_classification.py`),
and both feed it the evidence the ADR (§3bis) says the two pre-existing counters omit: the
service's real custom NGINX snippets and its real attached resources.

The thing these tests exist to stop is a "would qualify" on a service that something forbids.
A missing snippet or a missing attachment is the FAIL-OPEN direction -- it hands out a free
service -- so the evidence gathering is tested as hard as the rule it feeds, paging included.

`EXEMPTION_ENABLED` stays False throughout: a valid declaration is still billed. That is checked
here too, because "the conversion works" and "the conversion changes the bill" are separate
claims and only the first one is being made.

Same module-loader + stubbed-`sys.modules` pattern as `test_services_reserved.py`: there is no
live `TestClient` in `tests/unit/api`, so the handlers are called directly.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from fixtures.api_utils import load_api_utils
import schemas  # type: ignore

from default_server import DEFAULT_SERVER_ID  # type: ignore
from service_classification import EXEMPTION_ENABLED, MODE_REDIRECT_ONLY, MODE_STANDARD  # type: ignore

ROOT = Path(__file__).resolve().parents[3]

SERVICE = "app.example.com"
OTHER = "shop.example.com"


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    put = get
    patch = get
    delete = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_services": ModuleType("bw_services"),
        "bw_services.routers": ModuleType("bw_services.routers"),
        "bw_services.auth": ModuleType("bw_services.auth"),
        "bw_services.auth.guard": ModuleType("bw_services.auth.guard"),
        "bw_services.schemas": schemas,
        "bw_services.utils": ModuleType("bw_services.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_services"].__path__ = []
    names["bw_services.routers"].__path__ = []
    names["bw_services.auth"].__path__ = []
    names["bw_services.auth.guard"].guard = object()
    names["bw_services.utils"].get_db = Mock()
    names["bw_services.utils"].LOGGER = Mock()
    names["bw_services.utils"].reportable_config = load_api_utils().reportable_config
    http01_spec = importlib.util.spec_from_file_location("bw_services.http01", ROOT / "src" / "api" / "app" / "http01.py")
    http01 = importlib.util.module_from_spec(http01_spec)
    http01_spec.loader.exec_module(http01)
    names["bw_services.http01"] = http01
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "services.py"
        spec = importlib.util.spec_from_file_location("bw_services.routers.services", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()

# A service that carries NOTHING but a redirect: this is the profile the allowlist exists to
# accept. SERVE_FILES has to be turned off explicitly -- its plugin default is "yes", so leaving
# it out serves the document root on every path the redirect does not cover (ADR §5bis).
CLEAN_REDIRECT = {
    "REDIRECT_TO": "https://new.example.com",
    "SERVE_FILES": "no",
}


def _snapshot(services=None, **extra):
    """A `get_non_default_settings(global_only=False)` snapshot, service-prefixed."""
    services = services if services is not None else {SERVICE: dict(CLEAN_REDIRECT)}
    snapshot = {"SERVER_NAME": " ".join(services), "MULTISITE": "yes"}
    for name, settings in services.items():
        for key, value in settings.items():
            snapshot[f"{name}_{key}"] = value
    snapshot.update(extra)
    return snapshot


def _page(items, total=None):
    return {"items": items, "total": len(items) if total is None else total, "offset": 0, "limit": 500}


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    state = {"snapshot": _snapshot()}

    # A fresh dict per call: the handlers mutate the snapshot they are handed.
    fake_db.get_non_default_settings.side_effect = lambda *_args, **_kwargs: dict(state["snapshot"])
    fake_db.save_config.return_value = set()
    fake_db.is_multisite.return_value = True
    fake_db.get_services.return_value = [{"id": SERVICE, "method": "ui", "is_draft": False}]
    fake_db.get_custom_configs.return_value = []
    for accessor in ("get_redirects", "get_upstreams", "get_certificates", "get_workflows"):
        getattr(fake_db, accessor).return_value = _page([])
    fake_db.set_snapshot = lambda **kwargs: state.update(snapshot=_snapshot(**kwargs))
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def _written(db):
    """The config `_persist_config` was handed, or None when nothing was written."""
    return db.save_config.call_args[0][0] if db.save_config.call_args else None


# --------------------------------------------------------------------------------------
# POST /services/{id}/convert?mode=...
# --------------------------------------------------------------------------------------
class TestConversion:
    def test_a_clean_redirect_service_converts(self, db):
        response = ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        assert response.status_code == 200
        assert _written(db)[f"{SERVICE}_SERVICE_MODE"] == MODE_REDIRECT_ONLY

    def test_it_writes_exactly_one_setting(self, db):
        """The ADR's "explicit, never a side-effecting rewrite": a conversion never drops the
        capability it refused, and never touches anything else either."""
        before = _snapshot()
        ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        written = _written(db)
        assert set(written) - set(before) == {f"{SERVICE}_SERVICE_MODE"}
        assert {key: value for key, value in written.items() if key in before} == before

    def test_a_serving_capability_is_refused_with_its_reason(self, db):
        db.set_snapshot(services={SERVICE: dict(CLEAN_REDIRECT, USE_REVERSE_PROXY="yes")})

        response = ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        assert response.status_code == 409
        assert any("USE_REVERSE_PROXY" in reason for reason in response.content["reasons"])
        assert not db.save_config.called, "a refused conversion must write nothing"

    def test_a_custom_snippet_is_refused(self, db):
        """The anti-circumvention rule the classifier cannot see on its own (ADR §4): the snippet
        lives in another table, so the endpoint has to go and fetch it."""
        db.get_custom_configs.return_value = [{"service_id": SERVICE, "type": "server-http", "name": "extra"}]

        response = ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        assert response.status_code == 409
        assert any("custom config" in reason for reason in response.content["reasons"])

    def test_a_global_snippet_is_not_charged_to_the_service(self, db):
        """A fleet-wide snippet is attached to no service. Counting it would make the exemption
        unreachable on any real deployment, and the ADR forbids snippets attached TO the service."""
        db.get_custom_configs.return_value = [{"service_id": None, "type": "http", "name": "fleet"}]

        assert ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY).status_code == 200

    def test_a_forbidden_attachment_is_refused(self, db):
        """An upstream pool is proxying by another name, and it is attached, not configured -- so
        a settings-only judgement would never see it."""
        db.get_upstreams.return_value = _page([{"id": "u1", "services": [{"service_id": SERVICE, "match_path": "/"}]}])

        response = ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        assert response.status_code == 409
        assert any("upstream" in reason for reason in response.content["reasons"])

    def test_an_allowed_attachment_does_not_block(self, db):
        db.get_certificates.return_value = _page([{"id": "c1", "attachments": [{"service_id": SERVICE, "is_primary": True}]}])
        db.get_redirects.return_value = _page([{"id": "r1", "services": [SERVICE]}])

        assert ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY).status_code == 200

    def test_another_services_attachment_is_not_charged_to_this_one(self, db):
        db.get_workflows.return_value = _page([{"id": "w1", "services": [OTHER]}])

        assert ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY).status_code == 200

    def test_attachments_past_the_first_page_are_still_seen(self, db):
        """The accessors clamp `limit` to 500 and report the unpaged `total`. Trusting one page
        loses every attachment past it -- and a LOST attachment reads as "would qualify"."""
        pages = [
            {"items": [{"id": f"u{index}", "services": [{"service_id": OTHER, "match_path": "/"}]} for index in range(500)], "total": 501},
            {"items": [{"id": "u500", "services": [{"service_id": SERVICE, "match_path": "/"}]}], "total": 501},
        ]
        db.get_upstreams.side_effect = lambda **kwargs: pages[0] if kwargs.get("offset", 0) == 0 else pages[1]

        response = ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        assert response.status_code == 409, "the second page was never fetched"
        assert any("upstream" in reason for reason in response.content["reasons"])

    def test_reverting_to_standard_is_always_allowed(self, db):
        db.set_snapshot(services={SERVICE: {"USE_REVERSE_PROXY": "yes", "SERVICE_MODE": MODE_REDIRECT_ONLY}})

        response = ROUTER.convert_service(SERVICE, mode=MODE_STANDARD)

        assert response.status_code == 200
        assert _written(db)[f"{SERVICE}_SERVICE_MODE"] == MODE_STANDARD

    def test_the_reserved_default_server_has_no_mode(self, db):
        """It is the block that answers requests matching no service: neither billed nor
        exemptible. Refused BEFORE the service-exists check, like every other reserved refusal."""
        db.get_services.return_value = [{"id": DEFAULT_SERVER_ID, "method": "wizard", "is_draft": False}]

        response = ROUTER.convert_service(DEFAULT_SERVER_ID, mode=MODE_REDIRECT_ONLY)

        assert response.status_code == 403
        assert not db.save_config.called

    def test_an_unknown_service_is_refused(self, db):
        assert ROUTER.convert_service("nope.example.com", mode=MODE_REDIRECT_ONLY).status_code == 400

    def test_a_call_carrying_neither_axis_is_refused(self, db):
        response = ROUTER.convert_service(SERVICE)

        assert response.status_code == 400
        assert not db.save_config.called

    def test_the_draft_axis_still_works_on_its_own(self, db):
        """The regression guard: `mode` is additive, so the pre-existing two-argument call has to
        behave exactly as it did -- one row, IS_DRAFT, and no SERVICE_MODE."""
        response = ROUTER.convert_service(SERVICE, convert_to="draft")

        assert response.status_code == 200
        written = _written(db)
        assert written[f"{SERVICE}_IS_DRAFT"] == "yes"
        assert f"{SERVICE}_SERVICE_MODE" not in written

    def test_both_axes_in_one_call(self, db):
        ROUTER.convert_service(SERVICE, convert_to="online", mode=MODE_REDIRECT_ONLY)

        written = _written(db)
        assert written[f"{SERVICE}_IS_DRAFT"] == "no"
        assert written[f"{SERVICE}_SERVICE_MODE"] == MODE_REDIRECT_ONLY

    def test_the_exemption_gate_is_still_shut(self, db):
        """A guard, not a behavioural claim: `EXEMPTION_ENABLED` is False, so the conversion is
        validated and financially inert, and this endpoint must not be the thing that flips it
        (PO ruling, po-batch-19 item 1). What a valid declaration then classifies as is asserted
        against a real database in tests/unit/common/test_service_mode_anti_circumvention_e2e.py."""
        assert EXEMPTION_ENABLED is False


# --------------------------------------------------------------------------------------
# GET /services/redirect-candidates
# --------------------------------------------------------------------------------------
class TestCandidates:
    def _candidates(self):
        return ROUTER.redirect_candidates().content["candidates"]

    def test_a_clean_redirect_service_is_a_candidate(self, db):
        assert self._candidates() == [{"service": SERVICE, "would_qualify": True, "blocking_reasons": []}]

    def test_a_service_a_snippet_forbids_is_not_a_candidate(self, db):
        """The whole point of the audit fetching evidence: without the snippet this service reads
        as a clean redirect, and the badge would offer a saving the conversion then refuses."""
        db.get_custom_configs.return_value = [{"service_id": SERVICE, "type": "server-http", "name": "extra"}]

        candidate = self._candidates()[0]
        assert candidate["would_qualify"] is False
        assert any("custom config" in reason for reason in candidate["blocking_reasons"])

    def test_a_service_an_attachment_forbids_is_not_a_candidate(self, db):
        db.get_upstreams.return_value = _page([{"id": "u1", "services": [{"service_id": SERVICE, "match_path": "/"}]}])

        candidate = self._candidates()[0]
        assert candidate["would_qualify"] is False
        assert any("upstream" in reason for reason in candidate["blocking_reasons"])

    def test_the_reasons_are_reported_even_when_it_does_not_qualify(self, db):
        db.set_snapshot(services={SERVICE: dict(CLEAN_REDIRECT, USE_REVERSE_PROXY="yes")})

        candidate = self._candidates()[0]
        assert candidate["would_qualify"] is False
        assert any("USE_REVERSE_PROXY" in reason for reason in candidate["blocking_reasons"])

    def test_a_service_already_declared_redirect_only_is_not_listed(self, db):
        """There is nothing left to convert, so offering it is offering a saving already taken."""
        db.set_snapshot(services={SERVICE: dict(CLEAN_REDIRECT, SERVICE_MODE=MODE_REDIRECT_ONLY)})

        assert self._candidates() == []

    def test_the_reserved_default_server_is_never_a_candidate(self, db):
        db.set_snapshot(services={SERVICE: dict(CLEAN_REDIRECT), DEFAULT_SERVER_ID: dict(CLEAN_REDIRECT)})

        assert [row["service"] for row in self._candidates()] == [SERVICE]

    def test_the_audit_writes_nothing(self, db):
        self._candidates()

        assert not db.save_config.called

    def test_the_audit_and_the_conversion_agree(self, db):
        """One rule, two endpoints. A candidate the audit refuses must be refused by the write
        path, and one it accepts must be accepted -- otherwise the badge lies."""
        db.set_snapshot(services={SERVICE: dict(CLEAN_REDIRECT, USE_REVERSE_PROXY="yes")})
        refused = self._candidates()[0]
        response = ROUTER.convert_service(SERVICE, mode=MODE_REDIRECT_ONLY)

        assert refused["would_qualify"] is False
        assert response.status_code == 409
        assert response.content["reasons"] == refused["blocking_reasons"]
