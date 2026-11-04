import json
import logging
import os
import sys
import tarfile
import tempfile
import unittest
from contextlib import ExitStack
from io import BytesIO
from os import readlink
from pathlib import Path
from shutil import rmtree
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src/common/utils"), str(REPO_ROOT / "src/common/db")]

import cache_restore  # noqa: E402
import jobs  # noqa: E402
from Database import Database  # noqa: E402
from common_utils import safe_tar_extractall  # noqa: E402
from jobs import Job  # noqa: E402


def tree_snapshot(root: Path):
    snapshot = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", readlink(path))
        elif path.is_dir():
            snapshot[relative] = ("directory",)
        elif path.is_file():
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def tar_data(members):
    payload = BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        for member, content in members:
            if content is not None:
                member.size = len(content)
                archive.addfile(member, BytesIO(content))
            else:
                archive.addfile(member)
    return payload.getvalue()


def regular_member(name, content=b"bad"):
    return tarfile.TarInfo(name), content


def link_member(name, linkname, *, hard=False):
    member = tarfile.TarInfo(name)
    member.type = tarfile.LNKTYPE if hard else tarfile.SYMTYPE
    member.linkname = linkname
    return member, None


class CacheRestoreLinksTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        cache_root = self.root / "var/cache/bunkerweb"
        config_root = self.root / "etc/bunkerweb/configs"
        tmp_root = self.root / "var/tmp/bunkerweb"

        self.patches = ExitStack()
        self.patches.enter_context(patch.object(jobs, "sep", str(self.root)))
        self.patches.enter_context(patch.object(cache_restore, "CACHE_ROOT", cache_root))
        self.patches.enter_context(patch.object(cache_restore, "RESOLVED_CACHE_ROOT", cache_root.resolve()))
        self.patches.enter_context(patch.object(cache_restore, "CONFIG_ROOT", config_root))
        self.patches.enter_context(patch.object(cache_restore, "RESOLVED_CONFIG_ROOT", config_root.resolve()))
        self.patches.enter_context(patch.object(cache_restore, "TMP_ROOT", tmp_root))
        self.patches.enter_context(patch.object(cache_restore, "RESOLVED_TMP_ROOT", tmp_root.resolve()))
        self.patches.enter_context(patch.object(cache_restore, "FOLDER_ROOTS", (cache_root.resolve(), config_root.resolve(), tmp_root.resolve())))
        self.patches.enter_context(patch.dict(os.environ, {"DATABASE_URI_READONLY": ""}))

        self.logger = logging.getLogger("cache-restore-links-tests")
        self.database = Database(self.logger, sqlalchemy_string=f"sqlite:///{(self.root / 'database.sqlite3').as_posix()}")
        with (REPO_ROOT / "src/common/settings.json").open(encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        with (REPO_ROOT / "src/common/core/letsencrypt/plugin.json").open(encoding="utf-8") as plugin_file:
            plugin = json.load(plugin_file)
        initialized, error = self.database.init_tables([settings, plugin])
        self.assertTrue(initialized, error)
        self.assertEqual("", self.database.initialize_db(version="test", integration="Linux"))

        self.job = Job(self.logger, REPO_ROOT / "src/common/core/letsencrypt/jobs/certbot-new.py", db=self.database, deprecated=True)
        self.target = self.job.job_path / "certbot-cache"

    def tearDown(self):
        self.database.close()
        self.patches.close()
        self.tempdir.cleanup()

    def cache_and_restore(self):
        cached, error = self.job.cache_dir(self.target)
        self.assertTrue(cached, error)
        rmtree(self.target)
        self.assertTrue(self.job.restore_cache())

    def test_certbot_style_symlinks_round_trip_through_sqlite(self):
        files = {
            "cert": b"certificate bytes",
            "chain": b"chain bytes",
            "fullchain": b"full chain bytes",
            "privkey": b"private key bytes",
        }
        archive = self.target / "archive/example.test"
        live = self.target / "live/example.test"
        archive.mkdir(parents=True)
        live.mkdir(parents=True)
        for name, content in files.items():
            (archive / f"{name}1.pem").write_bytes(content)
            (live / f"{name}.pem").symlink_to(f"../../archive/example.test/{name}1.pem")

        self.cache_and_restore()

        for name, content in files.items():
            link = live / f"{name}.pem"
            self.assertTrue(link.is_symlink())
            self.assertEqual(content, link.read_bytes())

    def test_directory_symlink_round_trip_through_sqlite(self):
        directory = self.target / "archive/example.test"
        directory.mkdir(parents=True)
        (directory / "fullchain1.pem").write_bytes(b"full chain bytes")
        (self.target / "live").symlink_to("archive")

        self.cache_and_restore()

        link = self.target / "live/example.test/fullchain1.pem"
        self.assertTrue((self.target / "live").is_symlink())
        self.assertEqual(b"full chain bytes", link.read_bytes())

    def test_regular_file_archive_round_trip_through_sqlite(self):
        self.target.mkdir(parents=True)
        (self.target / "payload.txt").write_bytes(b"persistent cache payload")

        self.cache_and_restore()

        self.assertEqual(b"persistent cache payload", (self.target / "payload.txt").read_bytes())

    def test_malicious_archives_reject_and_preserve_last_good_tree(self):
        self.target.mkdir(parents=True)
        (self.target / "keep.txt").write_bytes(b"last good")
        before = tree_snapshot(self.target)
        companion = self.root / "companion.json"
        companion.write_bytes(b"last good companion")
        sentinel = self.root / "outside-sentinel"
        sentinel.write_bytes(b"unchanged")
        escaped_targets = {name: self.target.parent / name for name in ("x", "file", "outside")}
        for escaped_target in escaped_targets.values():
            escaped_target.write_bytes(b"unchanged")
        cases = (
            (
                "two-link escape",
                (link_member("anchor", "."), link_member("outside", "anchor/..")),
            ),
            (
                "two-link escape reverse order",
                (link_member("outside", "anchor/.."), link_member("anchor", ".")),
            ),
            ("absolute symlink target", (link_member("evil", "/outside"),)),
            ("direct escaping symlink", (link_member("link", "../outside"),)),
            ("hardlink", (link_member("hardlink", "target", hard=True),)),
            (
                "linked parent chain",
                (link_member("a", "."), link_member("b", "a/.."), regular_member("b/x")),
            ),
            ("symlinked parent dot", (link_member("parent", "."), regular_member("parent/file"))),
            ("symlinked parent dotdot", (link_member("parent", ".."), regular_member("parent/file"))),
            ("duplicate replacement", (link_member("same", "target"), regular_member("same"))),
            ("symlink cycle", (link_member("a", "b"), link_member("b", "a"))),
            ("parent traversal member", (regular_member("../escape.txt"),)),
            ("absolute member", (regular_member("/escape.txt"),)),
            ("device member", self._special_member("device", tarfile.CHRTYPE)),
            ("fifo member", self._special_member("pipe", tarfile.FIFOTYPE)),
        )

        for name, members in cases:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    cache_restore.restore_directory(self.target, tar_data(members), companion, b"new companion")
                self.assertEqual(before, tree_snapshot(self.target))
                self.assertEqual(b"last good companion", companion.read_bytes())
                self.assertEqual(b"unchanged", sentinel.read_bytes())
                for escaped_target in escaped_targets.values():
                    self.assertEqual(b"unchanged", escaped_target.read_bytes())
                self.assertFalse((self.target.parent / f".{self.target.name}.cache-backup").exists())
                self.assertFalse((self.target.parent / f".{self.target.name}.cache-journal").exists())
                self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.cache-staging-*")))

    @staticmethod
    def _special_member(name, member_type):
        member = tarfile.TarInfo(name)
        member.type = member_type
        return ((member, None),)

    def test_legacy_tar_extract_without_filter_parameter_uses_prevalidated_fallback(self):
        class LegacyTar:
            def __init__(self):
                self.called_path = None
                self.member = tarfile.TarInfo("cache")

            def getmembers(self):
                return [self.member]

            def extract(self, member, path, set_attrs=True, numeric_owner=False):
                self.called_path = path
                Path(path, member.name).touch()

        target = self.root / "legacy-target"
        target.mkdir()
        archive = LegacyTar()

        safe_tar_extractall(archive, target)

        self.assertEqual(target, archive.called_path)

    def test_stored_two_link_reproducer_refuses_restore_and_keeps_last_good(self):
        self.target.mkdir(parents=True)
        (self.target / "keep.txt").write_bytes(b"last good")
        before = tree_snapshot(self.target)
        sentinel = self.root / "outside-sentinel"
        sentinel.write_bytes(b"unchanged")

        cached, error = self.job.cache_dir(self.target)
        self.assertTrue(cached, error)
        malicious = tar_data((link_member("anchor", "."), link_member("outside", "anchor/..")))
        cached, error = self.job.cache_file(f"folder:{self.target}.tgz", malicious)
        self.assertTrue(cached, error)

        self.assertFalse(self.job.restore_cache())
        self.assertEqual(before, tree_snapshot(self.target))
        self.assertEqual(b"unchanged", sentinel.read_bytes())
        self.assertFalse((self.target.parent / f".{self.target.name}.cache-backup").exists())
        self.assertFalse((self.target.parent / f".{self.target.name}.cache-journal").exists())
        self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.cache-staging-*")))


if __name__ == "__main__":
    unittest.main()
