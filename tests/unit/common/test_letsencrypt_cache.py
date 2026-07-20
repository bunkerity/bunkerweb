"""Focused checks for read-only API-side Let's Encrypt cache inspection."""

from io import BytesIO
from tarfile import TarInfo, open as tar_open

import letsencrypt_cache


def _archive(files: dict[str, bytes]) -> bytes:
    content = BytesIO()
    with tar_open(fileobj=content, mode="w:gz") as archive:
        for name, data in files.items():
            member = TarInfo(name)
            member.size = len(data)
            member.mode = 0o600
            archive.addfile(member, BytesIO(data))
    return content.getvalue()


class _DB:
    def __init__(self, data: bytes, checksum="old-checksum"):
        self.data = data
        self.checksum = checksum

    def get_jobs_cache_files(self, *, job_name):
        assert job_name == "certbot-renew"
        return [{"file_name": letsencrypt_cache.LE_CACHE_FILE_NAME, "data": self.data, "checksum": self.checksum}]


def _cache() -> bytes:
    return _archive(
        {
            "accounts/acme.example/directory/present/regr.json": b"{}",
            "renewal/orphan.conf": b"account = missing\nserver = https://acme.example/directory\n",
            "live/orphan/fullchain.pem": b"orphan cert",
            "archive/orphan/cert1.pem": b"orphan archive",
            "renewal/healthy.conf": b"account = present\nserver = https://acme.example/directory\n",
            "live/healthy/fullchain.pem": b"healthy cert",
            "archive/healthy/cert1.pem": b"healthy archive",
            "renewal-hooks/post/reload": b"#!/bin/sh\n",
            "unrelated/provider-state.json": b'{"keep":true}',
        }
    )


def test_list_letsencrypt_orphans_is_read_only(tmp_path):
    db = _DB(_cache())

    assert letsencrypt_cache.list_letsencrypt_orphans(db, scratch_root=tmp_path) == [
        {"cert_name": "orphan", "account": "missing", "server": "https://acme.example/directory"}
    ]
