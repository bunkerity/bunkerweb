"""`acquire_lease` — a redelivery must be able to reclaim the lease its own kill orphaned.

push-configs releases its Redis lease in a `finally`, which a SIGKILL never runs, so a worker
killed mid-push leaves it held for up to LOCK_TTL (1800s). Delivery is at-least-once, so the very
next run is typically the redelivery of that same dispatch — and with the previous
timestamp-valued lease it read its own orphan as "another run is in flight", exited 0, and was
recorded as a SUCCESS while every instance carried on serving the old configuration.

The owner token is the Celery task id, which Celery preserves across a redelivery. That is the
whole mechanism: an owner match means "my own orphan" and can mean nothing else.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"


def _load_definitions():
    """Load definitions only — the module is a script that pushes configs and exits."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger", "jobs", "letsencrypt_consistency")}
    stubs["redis"].Redis = Mock()
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["Database"].Database = Mock()
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["jobs"]._write_atomic = Mock()
    stubs["letsencrypt_consistency"].le_cache_write_lock = Mock()

    module = ModuleType("bw_push_configs")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


PUSH = _load_definitions()
OWNER = "11111111-2222-3333-4444-555555555555"
OTHER = "99999999-8888-7777-6666-555555555555"


class FakeRedis:
    """Enough Redis to model SET NX / GET / SET on one key."""

    def __init__(self, held_by=None):
        self.value = held_by.encode() if held_by else None
        self.sets = []

    def set(self, key, value, nx=False, ex=None):
        self.sets.append({"key": key, "value": value, "nx": nx, "ex": ex})
        if nx and self.value is not None:
            return None
        self.value = value.encode() if isinstance(value, str) else value
        return True

    def get(self, key):
        return self.value


class TestFreeLease:
    def test_an_unheld_lease_is_taken(self):
        client = FakeRedis()
        assert PUSH.acquire_lease(client, OWNER, True) is True
        assert client.value == OWNER.encode()

    def test_it_is_taken_with_an_expiry_so_a_kill_cannot_hold_it_forever(self):
        """The `finally` that releases it does not run on SIGKILL, so the TTL is the only thing
        that eventually frees the lease for a *different* dispatch."""
        client = FakeRedis()
        PUSH.acquire_lease(client, OWNER, True)
        assert client.sets[0]["ex"] == PUSH.LOCK_TTL
        assert client.sets[0]["nx"] is True

    def test_the_owner_is_stored_not_a_timestamp(self):
        """A timestamp identifies nothing; reclaiming is only possible because the stored value
        names its owner."""
        client = FakeRedis()
        PUSH.acquire_lease(client, OWNER, True)
        assert client.value.decode() == OWNER


class TestReclaimingOwnOrphan:
    def test_a_lease_left_by_this_same_dispatch_is_reclaimed(self):
        """The bug this fixes: previously this returned False and the retry silently did nothing
        while being recorded as a success."""
        client = FakeRedis(held_by=OWNER)
        assert PUSH.acquire_lease(client, OWNER, True) is True

    def test_reclaiming_refreshes_the_expiry(self):
        """Otherwise the reclaimed lease keeps the dead run's remaining TTL and could expire
        underneath the push that is now genuinely in progress.

        Asserting on the LAST set is not enough: the failed `nx` attempt carries the same TTL,
        so that assertion stays true even with the refresh deleted. Look for a second,
        non-`nx` write instead -- that write IS the refresh.
        """
        client = FakeRedis(held_by=OWNER)
        PUSH.acquire_lease(client, OWNER, True)

        refreshes = [attempt for attempt in client.sets if not attempt["nx"]]
        assert len(refreshes) == 1
        assert refreshes[0]["value"] == OWNER
        assert refreshes[0]["ex"] == PUSH.LOCK_TTL


class TestSomeoneElsesLease:
    def test_a_lease_held_by_another_run_is_not_stolen(self):
        client = FakeRedis(held_by=OTHER)
        assert PUSH.acquire_lease(client, OWNER, True) is False
        assert client.value == OTHER.encode()

    def test_without_an_owner_token_nothing_is_ever_reclaimed(self):
        """bwcli and older workers export no task id. Then a held lease is always someone
        else's, which is the safe reading -- never guess."""
        client = FakeRedis(held_by=OWNER)
        assert PUSH.acquire_lease(client, OWNER, False) is False

    def test_a_lease_that_vanished_between_the_set_and_the_get_is_not_claimed(self):
        """`get` returning None after a failed `nx` set means it expired in between. Reporting
        success there would be a lie -- no lease is held. The next run takes it cleanly."""
        client = FakeRedis(held_by=OWNER)
        client.get = lambda key: None
        assert PUSH.acquire_lease(client, OWNER, True) is False


class TestOwnerDerivation:
    def test_the_job_takes_its_owner_from_the_worker_supplied_run_id(self):
        source = JOB_PATH.read_text(encoding="utf-8")
        assert 'getenv("BW_JOB_RUN_ID", "")' in source

    def test_a_missing_run_id_falls_back_to_a_value_that_cannot_match(self):
        """The fallback must be unique per process: a constant would let two unrelated runs
        reclaim each other's lease, which is worse than having no reclaim at all."""
        source = JOB_PATH.read_text(encoding="utf-8")
        assert 'lock_owner = run_id or f"anonymous-{uuid4()}"' in source


def test_the_worker_exports_the_id_this_job_reads():
    """The env var name is written in two files that never import each other, so nothing but a
    test connects them: the worker sets BW_JOB_RUN_ID, this job reads it, and a rename on either
    side would silently disable reclaiming rather than fail."""
    worker_source = (ROOT / "src" / "worker" / "tasks.py").read_text(encoding="utf-8")
    job_source = JOB_PATH.read_text(encoding="utf-8")

    assert 'os.environ["BW_JOB_RUN_ID"]' in worker_source
    assert "BW_JOB_RUN_ID" in job_source


def test_acknowledgement_never_clears_the_certificate_flag():
    db = Mock()
    db.clear_applied_changes.return_value = ""
    snapshot = {"certificates_changed": True}

    PUSH.acknowledge_changes(db, snapshot, "test")

    (passed_snapshot, keys), _ = db.clear_applied_changes.call_args
    assert passed_snapshot is snapshot
    assert "certificates" not in keys
    # The same call owns the per-plugin flags: this push is what applies a settings change,
    # and nothing else clears them, so autoconf's readiness gate waits out its 240s ceiling
    # on every configuration change when they are left set.
    assert "plugins_config" in keys


def test_only_enabled_plugins_are_materialized(tmp_path):
    disabled = tmp_path / "disabled"
    disabled.mkdir()
    db = Mock()
    db.get_plugins.return_value = []

    PUSH._materialize_plugins(db, tmp_path, pro=True)

    db.get_plugins.assert_called_once_with(_type="pro", with_data=True, only_enabled=True)
    assert not disabled.exists()


def test_each_instance_receives_its_own_api_token(tmp_path, monkeypatch):
    (tmp_path / "variables.env").write_bytes(b"SERVER_NAME=example.com\nAPI_TOKEN=global\n")
    seen = []
    monkeypatch.setattr(PUSH, "_build_api_caller", lambda instances: instances[0]["hostname"])
    monkeypatch.setattr(PUSH, "_write_atomic", lambda path, data: path.write_bytes(data))

    def capture(caller, source, endpoint):
        seen.append((caller, endpoint, source.joinpath("variables.env").read_bytes()))
        return True

    monkeypatch.setattr(PUSH, "_push_one_kind", capture)

    assert PUSH._push_configs([{"hostname": "a", "credential": "token-a"}, {"hostname": "b", "credential": "token-b"}], tmp_path)
    assert seen == [
        ("a", "/confs", b"SERVER_NAME=example.com\nAPI_TOKEN=token-a\n"),
        ("b", "/confs", b"SERVER_NAME=example.com\nAPI_TOKEN=token-b\n"),
    ]
