"""`PUT /configs/bulk` has to say whether the write LANDED, and 1.7 is where that gets decided.

`save_custom_configs` answers with one overloaded string: lines of the form
``Service <x> not found, please check your config`` are accumulated while the payload is written
and returned AFTER ``session.commit()`` -- the rows are in the database and the caller is only
being told that one of them references a service that does not exist. Anything else (a read-only
database, the empty-payload data-loss guard) means nothing was written at all.

The route mapped both onto an error status, and 500 for everything but "read-only". Two things
followed. `base_api_client` discards the body of a 5xx, so the caller received the bare string
``API returned 500`` with the reason gone; and dev `abb60b1ea`'s scheduler-side refusal predicate
-- which decides whether to regenerate ``/etc/bunkerweb/configs`` over an edit that is still only
on disk -- could not be ported at all, because on 1.7 the string never survives the hop. The
classification therefore lives here, at the last place that still has it. Port of dev `abb60b1ea`
(refused-write half), withdrawn from wave 13 for exactly this reason.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

import schemas  # type: ignore

ROOT = Path(__file__).resolve().parents[3]

ADVISORY = "Service app1.example.com not found, please check your config"
READONLY = "The database is read-only, the changes will not be saved"
# `db_methods/custom_configs.py`'s empty-payload data-loss guard. It used to return "" -- which the
# route answered 200 "success" with -- so this is the refusal that was invisible end to end.
EMPTY_PAYLOAD_REFUSAL = "Refusing to save custom configs: the ui payload is empty while 3 ui custom config(s) exist. Nothing was changed."


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
    def __init__(self, content=b"", *, status_code=200, media_type=None, headers=None):
        self.status_code = status_code
        self.body = content if isinstance(content, bytes) else str(content).encode()


class _JSONResponse(_Response):
    def __init__(self, *, status_code, content):
        super().__init__(json.dumps(content).encode(), status_code=status_code)


def _load_router():
    modules = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_configs": ModuleType("bw_configs"),
        "bw_configs.routers": ModuleType("bw_configs.routers"),
        "bw_configs.auth": ModuleType("bw_configs.auth"),
        "bw_configs.auth.guard": ModuleType("bw_configs.auth.guard"),
        "bw_configs.schemas": schemas,
        "bw_configs.utils": ModuleType("bw_configs.utils"),
    }
    for name in ("bw_configs", "bw_configs.routers", "bw_configs.auth", "bw_configs.auth.guard"):
        modules[name].__path__ = []
    modules["bw_configs.auth.guard"].guard = lambda: None
    modules["fastapi"].APIRouter = _Router
    modules["fastapi"].Depends = lambda dependency: dependency
    modules["fastapi"].File = lambda default=..., **_kwargs: default
    modules["fastapi"].Form = lambda default=..., **_kwargs: default
    modules["fastapi"].Query = lambda default=..., **_kwargs: default
    modules["fastapi"].Path = lambda default=..., **_kwargs: default
    modules["fastapi"].UploadFile = object
    modules["fastapi.responses"].JSONResponse = _JSONResponse
    modules["bw_configs.utils"].get_db = Mock()
    with patch.dict(sys.modules, modules):
        path = ROOT / "src" / "api" / "app" / "routers" / "configs.py"
        spec = importlib.util.spec_from_file_location("bw_configs.routers.configs", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _bulk(monkeypatch, returned):
    db = Mock()
    db.save_custom_configs.return_value = returned
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    request = Mock(custom_configs=[], method="manual", changed=True, disable_cleanup=False)
    response = ROUTER.bulk_save_custom_configs(request)
    return response.status_code, json.loads(response.body)


# --------------------------------------------------------------------------------------
# The predicate
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "message",
    [
        ADVISORY,
        f"{ADVISORY}\nService app2.example.com not found, please check your config",
        f"{ADVISORY}\n\n{ADVISORY}",
    ],
)
def test_a_message_made_only_of_the_post_commit_advisory_is_advisory(message):
    assert ROUTER._is_advisory_only(message)


@pytest.mark.parametrize(
    "message",
    [
        "",
        READONLY,
        EMPTY_PAYLOAD_REFUSAL,
        # The commit-failure exit prefixes the advisory onto the real error: one bad line poisons
        # the whole message, and it must not be read as "the write landed".
        f"{ADVISORY}\n(sqlite3.OperationalError) database is locked",
        "Service app1.example.com not found",  # truncated -- not the sentence the database emits
        "app1.example.com not found, please check your config",  # no prefix
    ],
)
def test_anything_else_is_a_refusal(message):
    assert not ROUTER._is_advisory_only(message)


# --------------------------------------------------------------------------------------
# What the route answers with
# --------------------------------------------------------------------------------------
def test_a_committed_write_with_an_advisory_is_a_success_that_carries_the_advisory(monkeypatch):
    """The rows are in the database. A 500 here made the UI flash "an error occurred" over a write
    that landed, and made the scheduler unable to tell the two apart at all."""
    status, body = _bulk(monkeypatch, ADVISORY)

    assert status == 200
    assert body["status"] == "success"
    assert body["message"] == ADVISORY


def test_a_refusal_is_a_4xx_that_states_the_reason(monkeypatch):
    """4xx and not 5xx on purpose: `base_api_client` keeps the body of a 4xx and throws away the
    body of a 5xx, which is how the reason used to be lost."""
    status, body = _bulk(monkeypatch, READONLY)

    assert 400 <= status < 500
    assert body == {"status": "error", "message": READONLY}


def test_a_clean_write_still_answers_a_bare_success(monkeypatch):
    status, body = _bulk(monkeypatch, "")

    assert status == 200
    assert body == {"status": "success"}


def test_no_outcome_of_this_route_is_a_5xx_any_more(monkeypatch):
    """The regression that mattered: every one of these is a thing the DATABASE reported, and a
    5xx is what discards the report."""
    for returned in ("", ADVISORY, READONLY, EMPTY_PAYLOAD_REFUSAL):
        status, _ = _bulk(monkeypatch, returned)
        assert status < 500, returned


def test_the_empty_payload_refusal_reaches_the_caller_as_a_4xx_that_states_it(monkeypatch):
    """Granted 2026-09-07 12:25 alongside the one-line `db_methods/custom_configs.py:74` change.
    That guard returned "" -- an empty return is SUCCESS to every caller -- so a write refused to
    prevent data loss was answered 200 `{"status": "success"}` here. Both halves are needed: the
    sentence alone with the old status mapping would still have been a 500 with the body dropped."""
    status, body = _bulk(monkeypatch, EMPTY_PAYLOAD_REFUSAL)

    assert status == 400
    assert body == {"status": "error", "message": EMPTY_PAYLOAD_REFUSAL}
