"""Self-signed generation survives a cache tree swap between cached files."""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory as _TemporaryDirectory
from types import SimpleNamespace
from typing import Tuple

ROOT = Path(__file__).resolve().parents[3]
JOB_SOURCE = ROOT / "src" / "common" / "core" / "selfsigned" / "jobs" / "self-signed.py"


def test_generated_files_are_cached_even_if_the_cache_tree_is_swapped(tmp_path):
    source = JOB_SOURCE.read_text(encoding="utf-8")
    start = source.index("def generate_cert(")
    end = source.index("\n\nstatus = 0", start)
    cache_root = tmp_path / "cache"

    class FakeJob:
        def __init__(self, cache_root):
            self.cache_root = cache_root
            self.results = []
            self.calls = []

        def cache_file(self, name, content, *, service_id="", overwrite_file=True):
            try:
                payload = content if isinstance(content, bytes) else Path(content).read_bytes()
            except FileNotFoundError as exc:
                self.results.append((name, False))
                return False, str(exc)

            self.calls.append((name, payload, isinstance(content, bytes)))
            self.results.append((name, True))
            cache_path = self.cache_root / service_id / name
            if overwrite_file or not cache_path.is_file():
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(payload)
            if len(self.calls) == 1:
                shutil.rmtree(cache_root, ignore_errors=True)
            return True, "success"

    def fake_run(command, **_kwargs):
        key_path = Path(command[command.index("-keyout") + 1])
        cert_path = Path(command[command.index("-out") + 1])
        key_path.write_bytes(b"private key")
        cert_path.write_bytes(b"certificate")
        return SimpleNamespace(returncode=0)

    job = FakeJob(cache_root)
    env = {
        "DEVNULL": object(),
        "JOB": job,
        "LOGGER": SimpleNamespace(info=lambda *_: None, warning=lambda *_: None, error=lambda *_: None),
        "Path": Path,
        "sep": str(tmp_path),
        "TemporaryDirectory": lambda **kwargs: _TemporaryDirectory(prefix=kwargs.get("prefix"), dir=tmp_path),
        "Tuple": Tuple,
        "getenv": lambda _key, default="": default,
        "multisite": False,
        "run": fake_run,
        "x509": SimpleNamespace(Certificate=object),
    }
    exec(compile(source[start:end], str(JOB_SOURCE), "exec"), env)  # noqa: S102

    result = env["generate_cert"]("www.example.com", "365", "/CN=www.example.com/", cache_root)

    assert result == (True, 1)
    assert job.results == [("cert.pem", True), ("key.pem", True)]
    assert job.calls == [
        ("cert.pem", b"certificate", True),
        ("key.pem", b"private key", True),
    ]


def test_regenerated_files_replace_existing_cache_files(tmp_path):
    source = JOB_SOURCE.read_text(encoding="utf-8")
    start = source.index("def generate_cert(")
    end = source.index("\n\nstatus = 0", start)
    cache_root = tmp_path / "cache"
    server_path = cache_root / "www.example.com"
    server_path.mkdir(parents=True)
    (server_path / "cert.pem").write_bytes(b"old certificate")
    (server_path / "key.pem").write_bytes(b"old private key")

    class FakeJob:
        def __init__(self):
            self.calls = []

        def cache_file(self, name, content, *, service_id="", overwrite_file=True):
            payload = content if isinstance(content, bytes) else Path(content).read_bytes()
            self.calls.append((name, payload, overwrite_file))
            cache_path = cache_root / service_id / name
            if overwrite_file or not cache_path.is_file():
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(payload)
            return True, "success"

    def fake_run(command, **_kwargs):
        if "-checkend" in command:
            return SimpleNamespace(returncode=1)
        key_path = Path(command[command.index("-keyout") + 1])
        cert_path = Path(command[command.index("-out") + 1])
        key_path.write_bytes(b"new private key")
        cert_path.write_bytes(b"new certificate")
        return SimpleNamespace(returncode=0)

    job = FakeJob()
    env = {
        "DEVNULL": object(),
        "JOB": job,
        "LOGGER": SimpleNamespace(info=lambda *_: None, warning=lambda *_: None, error=lambda *_: None),
        "Path": Path,
        "sep": str(tmp_path),
        "TemporaryDirectory": lambda **kwargs: _TemporaryDirectory(prefix=kwargs.get("prefix"), dir=tmp_path),
        "Tuple": Tuple,
        "getenv": lambda _key, default="": default,
        "multisite": False,
        "run": fake_run,
        "x509": SimpleNamespace(Certificate=object),
    }
    exec(compile(source[start:end], str(JOB_SOURCE), "exec"), env)  # noqa: S102

    result = env["generate_cert"]("www.example.com", "365", "/CN=www.example.com/", cache_root)

    assert result == (True, 1)
    assert job.calls == [
        ("cert.pem", b"new certificate", True),
        ("key.pem", b"new private key", True),
    ]
    assert (server_path / "cert.pem").read_bytes() == b"new certificate"
    assert (server_path / "key.pem").read_bytes() == b"new private key"
