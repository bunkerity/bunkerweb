"""Core plugin pages reading job caches through ``PLUGIN_API`` (`PX-UI`'s DB→API cutover).

Round 2: the round-1 tests mocked a shape ``get_cache_file`` never returns. The real client's
``download=True`` returns a ``requests.Response`` (`src/ui/app/api_client.py:159-164` ->
`src/common/utils/base_api_client.py:237-259`, proven by the one working caller,
`src/ui/app/routes/cache.py:51-52`'s ``resp.content``) and a missing file raises ``ApiClientError``
instead of returning ``None`` like the retired ``db.get_job_cache_file`` did
(`base_api_client.py:256`, `db_methods/jobs.py:254-255`). These tests go through the real
``PluginApi`` (not a bare ``MagicMock``) wrapping a fake client that returns exactly that shape, so
a regression in either `actions.py` or `PluginApi.get_cache_file_or_none` fails here.
"""

import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo, open as tar_open
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
_UI_ROOT = str(ROOT / "src" / "ui")
if _UI_ROOT not in sys.path:
    sys.path.insert(0, _UI_ROOT)

from app.api_client import ApiClientError  # noqa: E402
from app.plugin_api import PluginApi  # noqa: E402


def _actions(plugin):
    path = ROOT / "src" / "common" / "core" / plugin / "ui" / "actions.py"
    spec = importlib.util.spec_from_file_location(f"test_{plugin}_actions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tgz(members: dict) -> bytes:
    """A real gzip tar, no fixtures -- `members` maps an archive path to its bytes."""
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        for name, content in members.items():
            info = TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, BytesIO(content))
    return buf.getvalue()


class _FakeClient:
    """Stands in for the real ``ApiClient``: ``get_cache_file`` returns what
    ``base_api_client._raw_request`` actually returns (a ``Response``-shaped object exposing
    ``.content``) on ``download=True``, or raises ``ApiClientError(status_code=404)`` for a name
    that was never registered -- exactly what wraps ``PluginApi.get_cache_file_or_none`` here."""

    def __init__(self, *, cache_files=None, files=None):
        self.cache_files = cache_files or []
        self.files = files or {}  # (service, plugin, job, filename) -> bytes
        self.get_cache_files_calls = []
        self.get_cache_file_calls = []

    def get_cache_files(self, **kwargs):
        self.get_cache_files_calls.append(kwargs)
        return self.cache_files

    def get_cache_file(self, service, plugin, job, filename, download=False):
        self.get_cache_file_calls.append((service, plugin, job, filename, download))
        key = (service, plugin, job, filename)
        if key not in self.files:
            raise ApiClientError("Cache file not found", status_code=404)
        content = self.files[key]
        return SimpleNamespace(content=content) if download else content


# --------------------------------------------------------------------------------------
# Let's Encrypt -- the `folder:` archive, real extraction, real name (with slashes)
# --------------------------------------------------------------------------------------

FOLDER_NAME = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"
ENCODED_NAME = "folder:_var_cache_bunkerweb_letsencrypt_etc.tgz"


def test_letsencrypt_pre_render_downloads_and_extracts_the_real_archive(monkeypatch):
    actions = _actions("letsencrypt")
    archive = _tgz({"live/example.com/fullchain.pem": b"dummy-cert-bytes"})
    client = _FakeClient(
        cache_files=[{"file_name": FOLDER_NAME}],
        files={(None, "letsencrypt", "certbot-renew", ENCODED_NAME): archive},
    )
    seen = {}

    def fake_retrieve(folder_paths):
        (folder_path,) = folder_paths
        seen["extracted"] = folder_path.joinpath("live", "example.com", "fullchain.pem").read_bytes()
        return {"domain": ["example.com"]}

    monkeypatch.setattr(actions, "retrieve_certificates_info", fake_retrieve)

    result = actions.pre_render(None, api_client=PluginApi(client))

    assert "error" not in result
    assert result["list_certificates"]["data"]["domain"] == ["example.com"]
    assert seen["extracted"] == b"dummy-cert-bytes"
    assert client.get_cache_files_calls == [{"plugin": "letsencrypt", "job_name": "certbot-renew", "with_data": False}]
    assert client.get_cache_file_calls == [(None, "letsencrypt", "certbot-renew", ENCODED_NAME, True)]


def test_letsencrypt_pre_render_skips_a_folder_entry_whose_archive_is_gone(monkeypatch):
    """The archive listed but 404ing on download (purged between the list and the fetch) must not
    crash `extract_cache`'s `BytesIO(cache_file["data"])` -- it degrades to no certificates."""
    actions = _actions("letsencrypt")
    client = _FakeClient(cache_files=[{"file_name": FOLDER_NAME}], files={})
    monkeypatch.setattr(actions, "retrieve_certificates_info", lambda folder_paths: {"domain": []})

    result = actions.pre_render(None, api_client=PluginApi(client))

    assert "error" not in result
    assert result["list_certificates"]["data"]["domain"] == []


# --------------------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------------------


def test_backup_pre_render_reads_the_downloaded_bytes():
    actions = _actions("backup")
    client = _FakeClient(files={(None, "backup", "backup-data", "backup.json"): b'{"date": "2026-09-21", "files": ["backup.tar"]}'})

    result = actions.pre_render(api_client=PluginApi(client))

    assert "error" not in result
    assert result["date_last_backup"]["value"] == "2026-09-21"
    assert result["list_backup_files"]["data"] == {"file name": ["backup.tar"]}
    assert client.get_cache_file_calls == [(None, "backup", "backup-data", "backup.json", True)]


def test_backup_pre_render_has_no_backup_yet_without_an_error():
    """A fresh install never ran the `backup-data` job: 404, not a crash."""
    actions = _actions("backup")
    client = _FakeClient(files={})

    result = actions.pre_render(api_client=PluginApi(client))

    assert "error" not in result
    assert result["date_last_backup"]["value"] == "N/A"
    assert result["list_backup_files"]["data"] == {}


# --------------------------------------------------------------------------------------
# BunkerNet
# --------------------------------------------------------------------------------------


def test_bunkernet_pre_render_reads_the_downloaded_bytes():
    actions = _actions("bunkernet")
    client = _FakeClient(
        files={
            (None, "bunkernet", "bunkernet-register", "instance.id"): b"instance-1",
            (None, "bunkernet", "bunkernet-data", "ip.list"): b"192.0.2.1\n",
        }
    )
    instances = SimpleNamespace(get_ping=lambda _svc: {"status": "success", "msg": "using instance ID instance-1 is successful"})

    result = actions.pre_render(api_client=PluginApi(client), bw_instances_utils=instances)

    assert "error" not in result
    assert result["info_instance_id"]["value"] == "instance-1"
    assert result["list_bunkernet_ips"]["data"] == {"ip": ["192.0.2.1", ""]}
    assert client.get_cache_file_calls == [
        (None, "bunkernet", "bunkernet-register", "instance.id", True),
        (None, "bunkernet", "bunkernet-data", "ip.list", True),
    ]


def test_bunkernet_pre_render_not_registered_yet_without_an_error():
    """`bunkernet-register` has never run on a fresh install: 404 on `instance.id`, and the page
    must tell that state apart from a real API failure -- not raise `ret["error"]`."""
    actions = _actions("bunkernet")
    client = _FakeClient(files={})
    instances = SimpleNamespace(get_ping=lambda _svc: {"status": "error", "msg": ""})

    result = actions.pre_render(api_client=PluginApi(client), bw_instances_utils=instances)

    assert "error" not in result
    assert result["info_connectivity"]["value"] == "Not registered yet"
    # The IP list is only ever fetched once an instance ID exists.
    assert client.get_cache_file_calls == [(None, "bunkernet", "bunkernet-register", "instance.id", True)]
