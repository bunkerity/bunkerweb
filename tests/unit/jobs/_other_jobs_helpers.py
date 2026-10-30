"""Execute complete jobs with temporary system paths and blocked external I/O."""

import importlib.util
import logging
import os
import pathlib
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

import cache_restore  # noqa: F401 -- bind shared helpers to the real pathlib before scoping scripts
import certificate_validation  # noqa: F401
import common_utils
from common_utils import bytes_hash

ROOT = pathlib.Path(os.environ.get("BW_C2_SOURCE_ROOT", pathlib.Path(__file__).resolve().parents[3]))


class Cache:
    def __init__(self, root):
        self.job_path = root
        self.job_path.mkdir(parents=True, exist_ok=True)
        self.data = {}
        self.restore_ok = True
        self.job_name = "unit-job"
        self.db = Mock()
        self.db.get_job_cache_file.return_value = None
        self.db.upsert_job_caches.return_value = ""

    def cache_file(self, name, data, service_id="", **kwargs):
        if isinstance(data, pathlib.Path):
            data = data.read_bytes()
        path = self.job_path / service_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.data[service_id, name] = data
        return True, ""

    def get_cache(self, name, service_id="", **kwargs):
        data = self.data.get((service_id, name))
        if data is None:
            return None
        if not kwargs.get("with_info"):
            return data
        return {"data": data, "last_update": time.time(), "path": self.job_path / service_id / name}

    def cache_hash(self, name, service_id=""):
        data = self.data.get((service_id, name))
        return bytes_hash(data) if data is not None else None

    def del_cache(self, name, service_id=""):
        path = name if isinstance(name, pathlib.Path) else self.job_path / service_id / name
        self.data.pop((service_id, path.name), None)
        path.unlink(missing_ok=True)
        return True, ""


def load_job(monkeypatch, tmp_path, relative, *, env=None, cache=None, database=None, get=None, post=None):
    """Use the real script loader; remap absolute runtime paths before its body executes."""
    cache = cache or Cache(tmp_path / "cache")
    for key in list(os.environ):
        if key in ("SERVER_NAME", "MULTISITE", "EXTERNAL_PLUGIN_URLS", "PRO_LICENSE_KEY") or any(
            term in key for term in ("ROBOTSTXT", "DNSBL", "REVERSE_PROXY", "GRPC", "MTLS", "SELF_SIGNED", "MODSECURITY")
        ):
            monkeypatch.delenv(key)
    for key, value in {"SERVER_NAME": "app.example alias.example", "MULTISITE": "no", **(env or {})}.items():
        monkeypatch.setenv(key, value)

    class ScopedPath(type(pathlib.Path())):
        def __init__(self, *parts):
            path = pathlib.Path(*parts)
            if str(path).startswith(("/etc/bunkerweb", "/var/cache/bunkerweb", "/var/tmp/bunkerweb", "/usr/share/bunkerweb")):
                path = tmp_path / "system" / path.relative_to("/")
            super().__init__(path)

    scoped_pathlib = ModuleType("pathlib")
    scoped_pathlib.__dict__.update(vars(pathlib))
    scoped_pathlib.Path = ScopedPath
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *_args, **_kwargs: cache))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=logging.getLogger))
    if database is not None:
        monkeypatch.setitem(sys.modules, "Database", SimpleNamespace(Database=lambda *_args, **_kwargs: database))

    def blocked(*args, **kwargs):
        raise AssertionError(f"Unexpected external request: {args}")

    monkeypatch.setattr(requests, "get", get or blocked)
    monkeypatch.setattr(requests, "post", post or blocked)
    monkeypatch.setattr(requests, "head", blocked)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(common_utils, "get_version", lambda: "1.6.18")
    monkeypatch.setattr(common_utils, "get_os_info", lambda: {"id": "unit"})
    monkeypatch.setattr(common_utils, "get_integration", lambda: "Docker")
    monkeypatch.setitem(sys.modules, "magic", SimpleNamespace(Magic=lambda **_: SimpleNamespace(from_buffer=lambda _: "application/octet-stream")))
    spec = importlib.util.spec_from_file_location("bw_other_job", ROOT / "src/common/core" / relative)
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as scoped:
        scoped.setitem(sys.modules, "pathlib", scoped_pathlib)
        with pytest.raises(SystemExit) as stopped:
            spec.loader.exec_module(module)
    return module, stopped.value.code
