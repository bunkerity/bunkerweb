import sys
import unittest
from os import environ
from pathlib import PosixPath
from runpy import run_path
from subprocess import PIPE, run
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import MagicMock, patch

REPO_ROOT = PosixPath(__file__).resolve().parents[2]
SCRIPT = PosixPath(environ.get("DEFAULT_SERVER_CERT_SCRIPT", REPO_ROOT / "src/common/core/misc/jobs/default-server-cert.py"))
REAL_PATH = PosixPath


class FakeDatabase:
    """Rows keyed by file name. The per-row upsert fails on its second call, the batch upsert is all or nothing."""

    def __init__(self):
        self.rows = {}
        self.row_calls = 0

    def upsert_job_cache(self, service_id, file_name, data, *, job_name=None, checksum=None):
        self.row_calls += 1
        if self.row_calls == 2:
            return "An error occurred while saving job caches"
        self.rows[file_name] = data
        return ""

    def upsert_job_caches(self, entries, *, deletions=()):
        self.rows.update({entry["file_name"]: entry["data"] for entry in entries})
        return ""


class FakeJob:
    job_name = "default-server-cert"

    def __init__(self, *args, **kwargs):
        self.db = FAKE_DB

    def is_cached_file(self, *args, **kwargs):
        return False

    def cache_file(self, name, file_cache, *, overwrite_file=True, **kwargs):
        err = self.db.upsert_job_cache("", name, PosixPath(file_cache).read_bytes(), job_name=self.job_name)
        return not err, err or "success"


FAKE_DB = FakeDatabase()
LOGGER_MOCK = MagicMock()


def pubkey(args, data):
    return run(["openssl", *args], input=data, stdout=PIPE, check=True).stdout


class DefaultServerCertPairTest(unittest.TestCase):
    def run_job(self):
        global FAKE_DB
        FAKE_DB = FakeDatabase()
        with TemporaryDirectory() as root:

            def rooted_path(*parts):
                # The job hard-codes /var/cache/bunkerweb/misc: move it under the temporary root.
                if len(parts) > 1 and parts[0] == "/":
                    return REAL_PATH(root, *parts[1:])
                return REAL_PATH(*parts)

            modules = {name: ModuleType(name) for name in ("common_utils", "logger", "jobs")}
            modules["common_utils"].bytes_hash = lambda data: str(hash(data))
            modules["logger"].getLogger = lambda name: LOGGER_MOCK
            modules["jobs"].Job = FakeJob
            with patch.dict(sys.modules, modules), patch("pathlib.Path", rooted_path):
                with self.assertRaises(SystemExit):
                    run_path(str(SCRIPT), run_name="__main__")
            misc = REAL_PATH(root, "var/cache/bunkerweb/misc")
            return misc.joinpath("default-server-cert.pem").read_bytes(), misc.joinpath("default-server-cert.key").read_bytes()

    def test_cached_rows_are_one_generation(self):
        cert, key = self.run_job()
        self.assertEqual(pubkey(["x509", "-noout", "-pubkey"], cert), pubkey(["pkey", "-pubout"], key), "files on disk do not match")
        rows = FAKE_DB.rows
        # A failed save may leave the database empty, never holding only one member of the pair.
        self.assertIn(len(rows), (0, 2), f"database holds a partial pair: {sorted(rows)}")
        if rows:
            self.assertEqual(
                pubkey(["x509", "-noout", "-pubkey"], rows["default-server-cert.pem"]), pubkey(["pkey", "-pubout"], rows["default-server-cert.key"])
            )


if __name__ == "__main__":
    unittest.main()
