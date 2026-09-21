"""``GET /cache/.../{file_name}`` for a ``folder:``-prefixed cache row.

``cache_dir`` stores directory snapshots with the ``folder:`` prefix INCLUDED in ``file_name``
(``src/common/utils/jobs.py:609``: ``file_name = f"folder:{dir_path.as_posix()}.tgz"``), and the
lookup filters that column with an exact match (``src/common/db/db_methods/jobs.py:245``). The
router's path-token decoder used to strip the prefix it had just decoded
(``path_token.replace("_", "/")[len("folder:"):]``), so the decoded name never matched the stored
row and every folder-backed cache file (e.g. the Let's Encrypt live/archive/renewal snapshot) 404'd
forever. The fix keeps the prefix: callers now send the ENCODED token (`folder:_var_...`, one path
segment, no literal ``/``) and the router decodes it back to the stored name.

This does NOT make ``src/ui/app/routes/cache.py:42-43`` work -- that caller decodes to slashes
*before* calling the client, so it can never reach this route at all (one FastAPI path segment
cannot contain ``/``). That caller is still broken; out of this lane's scope, tracked in
``followup-LE-PAGE.md``.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import schemas  # type: ignore  # noqa: E402 -- on sys.path via tests/unit/api/conftest.py

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    delete = get


class _Response:
    def __init__(self, content=b"", *, status_code=200, media_type=None, headers=None):
        self.status_code = status_code
        self.body = content if isinstance(content, bytes) else str(content).encode()
        self.media_type = media_type
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}


class _JSONResponse(_Response):
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_cache": ModuleType("bw_cache"),
        "bw_cache.routers": ModuleType("bw_cache.routers"),
        "bw_cache.auth": ModuleType("bw_cache.auth"),
        "bw_cache.auth.guard": ModuleType("bw_cache.auth.guard"),
        "bw_cache.schemas": schemas,
        "bw_cache.utils": ModuleType("bw_cache.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _JSONResponse
    names["fastapi.responses"].Response = _Response
    names["bw_cache"].__path__ = []
    names["bw_cache.routers"].__path__ = []
    names["bw_cache.auth"].__path__ = []
    names["bw_cache.auth.guard"].guard = object()
    names["bw_cache.utils"].get_db = lambda: None
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "cache.py"
        spec = importlib.util.spec_from_file_location("bw_cache.routers.cache", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()

STORED_NAME = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"
ENCODED_NAME = "folder:_var_cache_bunkerweb_letsencrypt_etc.tgz"


class _FakeDB:
    """Mimics the exact-match filter `Jobs_cache` lookup really performs
    (`src/common/db/db_methods/jobs.py:245`): only the row keyed by the exact stored
    `file_name` (prefix included) answers; anything else is a miss, like the real filter."""

    def __init__(self, stored: dict):
        self.stored = stored
        self.calls = []

    def delete_job_cache(self, file_name, *, job_name, service_id=""):
        # Same exact-match miss semantics as `Jobs_cache` delete (`db_methods/jobs.py:104-122`):
        # a miss deletes nothing and returns "" -- the caller cannot tell the difference.
        self.calls.append({"op": "delete", "job_name": job_name, "file_name": file_name, "service_id": service_id})
        self.stored.pop(file_name, None)
        return ""

    def checked_changes(self, **_kwargs):
        return None

    def get_job_cache_file(self, job_name, file_name, *, service_id="", plugin_id="", with_info=False, with_data=True):
        self.calls.append({"job_name": job_name, "file_name": file_name, "service_id": service_id, "plugin_id": plugin_id})
        if file_name not in self.stored:
            return None
        payload = {"data": self.stored[file_name]}
        if with_info:
            payload["last_update"] = None
            payload["checksum"] = "deadbeef"
        return payload


def test_transform_filename_keeps_the_folder_prefix():
    assert ROUTER._transform_filename(ENCODED_NAME) == STORED_NAME


def test_transform_filename_is_a_no_op_for_plain_names():
    assert ROUTER._transform_filename("backup.json") == "backup.json"


def test_fetch_cache_file_resolves_a_folder_prefixed_name(monkeypatch):
    db = _FakeDB({STORED_NAME: b"tarball-bytes"})
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.fetch_cache_file("global", "letsencrypt", "certbot-renew", ENCODED_NAME, download=True)

    assert response.status_code == 200
    assert response.body == b"tarball-bytes"
    # The DB was queried with the exact stored name -- prefix included, proving the round trip.
    assert db.calls == [{"job_name": "certbot-renew", "file_name": STORED_NAME, "service_id": "", "plugin_id": "letsencrypt"}]


def test_fetch_cache_file_404s_when_the_name_genuinely_does_not_match(monkeypatch):
    db = _FakeDB({})
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.fetch_cache_file("global", "letsencrypt", "certbot-renew", ENCODED_NAME, download=True)

    assert response.status_code == 404


def test_delete_cache_files_reaches_the_db_with_the_stored_name(monkeypatch):
    # The /cache page sends the RAW stored name (anchor text, slashes intact); it must reach
    # `delete_job_cache` unchanged so the row really goes -- before the prefix fix this call
    # deleted nothing while the UI still reported success.
    db = _FakeDB({STORED_NAME: b"tarball-bytes"})
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    payload = schemas.CacheFilesDeleteRequest(cache_files=[{"service": "global", "plugin": "letsencrypt", "jobName": "certbot-renew", "fileName": STORED_NAME}])

    response = ROUTER.delete_cache_files(payload)

    assert response.status_code == 200
    assert response.content["deleted"] == 1
    assert db.calls == [{"op": "delete", "job_name": "certbot-renew", "file_name": STORED_NAME, "service_id": None}]
    assert STORED_NAME not in db.stored
