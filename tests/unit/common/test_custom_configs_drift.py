"""``custom_configs_drift`` — the edges the two projection tests do not reach.

The scheduler and worker suites cover the two policies end to end. What is left here is the
detector's own perimeter, which decides how noisy the log is in production: what counts as a
projected file, what is deliberately ignored, and how a bad policy value is read.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from custom_configs_drift import (  # type: ignore
    DEFAULT_DRIFT_POLICY,
    ConfigDrift,
    custom_config_path,
    detect_drift,
    get_drift_policy,
    log_drift,
    log_refusal,
    read_projection,
    write_projection,
)


def _manifest(root, *relatives):
    """The manifest the projection would have left behind for these files."""
    from custom_configs_drift import _short  # type: ignore

    return {rel: _short(Path(root).joinpath(rel).read_bytes()) for rel in relatives}


def _config(name, data, *, _type="http", service_id=None, method="manual", is_draft=False):
    return {"service_id": service_id, "type": _type, "name": name, "data": data, "method": method, "is_draft": is_draft}


class TestGetDriftPolicy:
    @pytest.mark.parametrize("raw", ["overwrite", "OVERWRITE", " refuse ", "refuse"])
    def test_known_values_are_normalized(self, raw):
        assert get_drift_policy(raw) in ("overwrite", "refuse")
        assert get_drift_policy(raw) == raw.strip().lower()

    @pytest.mark.parametrize("raw", ["", "adopt", "yes", "Refuse!", None])
    def test_anything_else_is_the_default(self, raw, monkeypatch):
        """``adopt`` is in that list on purpose: it was proposed and rejected -- it would let a
        hand edit beat ``CUSTOM_CONF_*``, which is what config-as-code exists to prevent. An
        operator who sets it must get today's behaviour, not a silent third mode."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        assert get_drift_policy(raw) == DEFAULT_DRIFT_POLICY == "overwrite"

    def test_it_falls_back_to_the_environment(self, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        assert get_drift_policy() == "refuse"


class TestCustomConfigPath:
    def test_the_type_is_hyphenated_and_the_extension_normalized(self):
        assert custom_config_path("/root", _config("snippet.conf", b"", _type="server_http")) == Path("/root/server-http/snippet.conf")

    def test_a_service_config_gets_its_own_level(self):
        path = custom_config_path("/root", _config("s", b"", _type="modsec_crs", service_id="app1.example.com"))
        assert path == Path("/root/modsec-crs/app1.example.com/s.conf")


class TestDetectDriftPerimeter:
    def test_a_missing_folder_is_not_drift(self, tmp_path):
        assert detect_drift(tmp_path / "absent", [_config("a", b"x")], {}) == []

    def test_a_non_conf_file_is_ignored(self, tmp_path):
        """Only ``*.conf`` is projected, and only ``*.conf`` can be adopted by the scheduler's
        rescan -- naming a ``foo.conf~`` left by an editor would be a line about a file the
        operator has no way to keep."""
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "leftover.conf~").write_bytes(b"# editor backup\n")

        assert detect_drift(tmp_path, [], {}) == []

    def test_a_symlink_is_never_followed(self, tmp_path):
        """The projection unlinks symlinks, but reading through one would leave the tree."""
        outside = tmp_path.joinpath("outside.conf")
        outside.write_bytes(b"# not ours\n")
        tmp_path.joinpath("configs", "http").mkdir(parents=True)
        tmp_path.joinpath("configs", "http", "link.conf").symlink_to(outside)

        assert detect_drift(tmp_path / "configs", [], {}) == []

    def test_a_file_three_levels_down_is_out_of_scope(self, tmp_path):
        """``check_configs_changes`` already refuses that depth; the generator never writes it."""
        deep = tmp_path.joinpath("http", "app1.example.com", "nested")
        deep.mkdir(parents=True)
        deep.joinpath("too-deep.conf").write_bytes(b"# nope\n")

        assert detect_drift(tmp_path, [], {}) == []

    def test_a_row_with_empty_data_projects_nothing_so_its_file_is_an_orphan(self, tmp_path):
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "empty.conf").write_bytes(b"# on disk\n")

        drifts = detect_drift(tmp_path, [_config("empty", b"")], {})

        assert [d.reason for d in drifts] == ["orphan"]

    def test_string_data_compares_equal_to_the_same_bytes(self, tmp_path):
        """``get_custom_configs`` hands back bytes, but the UI/API payloads carry ``str``; a
        mismatch here would report every config as drifted on whichever path uses the other."""
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "s.conf").write_bytes(b"# same\n")

        assert detect_drift(tmp_path, [_config("s", "# same\n")], _manifest(tmp_path, "http/s.conf")) == []


class TestLogDrift:
    def test_the_checksums_differ_between_the_two_halves(self, tmp_path):
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "s.conf").write_bytes(b"# disk\n")
        logger = Mock()

        drifts = log_drift(logger, tmp_path, [_config("s", b"# db\n", method="ui")], "overwrite", {"http/s.conf": "0" * 12})

        assert len(drifts) == 1
        drift = drifts[0]
        assert isinstance(drift, ConfigDrift)
        assert drift.disk_checksum != drift.db_checksum
        assert len(drift.disk_checksum) == 12
        assert logger.warning.call_count == 1

    def test_nothing_is_logged_when_nothing_drifted(self, tmp_path):
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "s.conf").write_bytes(b"# same\n")
        logger = Mock()

        assert log_drift(logger, tmp_path, [_config("s", b"# same\n")], "overwrite", _manifest(tmp_path, "http/s.conf")) == []
        logger.warning.assert_not_called()


class TestLogRefusalTellsTheTruth:
    """The refusal ERROR is the only thing the operator reads, so it must not contradict what the
    code does.

    Two claims an earlier wording got wrong. First, "the last good projection is kept" reads as
    "only the drifted file is held back" — but the projection returns before the write loop, so
    **nothing** from the database is written, including configs that have nothing to do with the
    drift. Second, on all-in-one and Linux this folder is the one NGINX includes
    (`all-in-one/Dockerfile` symlinks it to `/data/configs`; the instance's own `/custom_configs`
    handler unpacks into the same path, `src/bw/lua/bunkerweb/api.lua`), so the drifted files are
    what is being served — the opposite of "kept safe out of the way".
    """

    @staticmethod
    def _message(tmp_path):
        logger = Mock()
        drift = ConfigDrift(tmp_path / "http" / "s.conf", "modified", "scheduler", "aaaaaaaaaaaa", "bbbbbbbbbbbb")
        log_refusal(logger, tmp_path, [drift])
        assert logger.error.call_count == 1
        return logger.error.call_args[0][0]

    def test_it_says_nothing_was_written_not_that_a_projection_was_kept(self, tmp_path):
        message = self._message(tmp_path)

        assert "NOTHING was written" in message
        assert "last good projection" not in message

    def test_it_says_the_change_is_not_being_applied(self, tmp_path):
        assert "no custom config change is being applied" in self._message(tmp_path)

    def test_it_warns_that_the_drifted_files_are_the_ones_served(self, tmp_path):
        message = self._message(tmp_path)

        assert "all-in-one and Linux" in message
        assert "NGINX includes" in message

    def test_it_names_every_drifted_path_and_both_ways_out(self, tmp_path):
        message = self._message(tmp_path)

        assert (tmp_path / "http" / "s.conf").as_posix() in message
        assert "deleting the file" in message
        assert "adopt" in message


class TestDriftIsMeasuredAgainstTheProjectionNotTheDatabase:
    """The defect Criticos round 2 found: comparing the folder against the *current* rows cannot
    tell an operator edit from a folder that has not caught up yet.

    Every ordinary change — someone saves a config in the web UI, a `CUSTOM_CONF_*` variable moves,
    a row is deleted — leaves the folder holding the previous projection while the rows already
    hold the new content. Reported as drift, that makes the WARNING fire on every legitimate change
    and makes `refuse` refuse the very change it was asked to protect, permanently: the flag never
    clears, so the scheduler re-dispatches the push every APPLY_RETRY_INTERVAL forever.

    The manifest is what separates the two. Drift means "changed under us since we wrote it".
    """

    def test_a_stale_projection_of_a_changed_row_is_not_drift(self, tmp_path):
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "foo.conf").write_bytes(b"# v1\n")
        projection = _manifest(tmp_path, "http/foo.conf")  # what the last projection wrote

        # the operator edits it in the WEB UI: the row now holds v2, nobody touched the disk
        drifts = detect_drift(tmp_path, [_config("foo", b"# v2\n", method="ui")], projection)

        assert drifts == [], "a pending update is not drift"

    def test_a_hand_edit_of_the_same_file_still_is_drift(self, tmp_path):
        """The other half — without this, the manifest would have disabled the feature."""
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "foo.conf").write_bytes(b"# v1\n")
        projection = _manifest(tmp_path, "http/foo.conf")
        tmp_path.joinpath("http", "foo.conf").write_bytes(b"# OPERATOR EDIT\n")

        drifts = detect_drift(tmp_path, [_config("foo", b"# v1\n", method="scheduler")], projection)

        assert [d.reason for d in drifts] == ["modified"]

    def test_a_deleted_row_does_not_strand_its_own_projection(self, tmp_path):
        """A deletion leaves the file behind until the next wipe. That is the projection's own
        output, not an operator's, so it is removed quietly — `orphan` is for files WE never wrote."""
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "gone.conf").write_bytes(b"# once in the database\n")
        projection = _manifest(tmp_path, "http/gone.conf")

        assert detect_drift(tmp_path, [], projection) == []

    def test_a_file_the_projection_never_wrote_is_an_orphan(self, tmp_path):
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "dropped.conf").write_bytes(b"# dropped by hand\n")

        drifts = detect_drift(tmp_path, [], {})

        assert [d.reason for d in drifts] == ["orphan"]

    def test_an_unknown_history_reports_nothing_at_all(self, tmp_path):
        """`None` is not `{}`. A fresh install, an upgrade and a recreated container all start with
        no manifest, and must behave exactly as they did before rather than declare the whole
        folder drifted."""
        tmp_path.joinpath("http").mkdir()
        tmp_path.joinpath("http", "foo.conf").write_bytes(b"# anything\n")

        assert detect_drift(tmp_path, [_config("foo", b"# different\n")], None) == []


class TestProjectionManifest:
    def test_it_round_trips_what_is_on_disk(self, tmp_path):
        root = tmp_path / "configs"
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "a.conf").write_bytes(b"# a\n")
        root.joinpath("server-http", "app1.example.com").mkdir(parents=True)
        root.joinpath("server-http", "app1.example.com", "b.conf").write_bytes(b"# b\n")
        state = tmp_path / "state.json"

        write_projection(root, state)

        assert read_projection(state) == _manifest(root, "http/a.conf", "server-http/app1.example.com/b.conf")
        assert detect_drift(root, [], read_projection(state)) == [], "its own output is never drift"

    def test_a_missing_manifest_reads_as_unknown_not_empty(self, tmp_path):
        assert read_projection(tmp_path / "nope.json") is None

    def test_a_corrupt_manifest_reads_as_unknown(self, tmp_path):
        """Advisory, never load-bearing: a damaged file must disable detection, not break a reload."""
        state = tmp_path / "state.json"
        state.write_text("{not json", encoding="utf-8")

        assert read_projection(state) is None

    def test_a_manifest_without_a_files_map_reads_as_unknown(self, tmp_path):
        state = tmp_path / "state.json"
        state.write_text('{"root": "/etc/bunkerweb/configs"}', encoding="utf-8")

        assert read_projection(state) is None

    def test_an_unwritable_location_is_not_fatal(self, tmp_path):
        """Losing the manifest costs the next pass its detection, never the projection itself.

        The location has to be one ``mkdir(parents=True, exist_ok=True)`` cannot conjure, or the
        test proves nothing: a merely missing parent IS created by `write_projection` itself. A
        parent that exists and is a FILE makes `mkdir` re-raise the `FileExistsError` that
        `exist_ok` would otherwise swallow (it only swallows it for an existing *directory*), and
        `FileExistsError` is an `OSError`.
        """
        root = tmp_path / "configs"
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "a.conf").write_bytes(b"# a\n")
        blocker = tmp_path / "a-file-not-a-directory"
        blocker.write_text("", encoding="utf-8")

        write_projection(root, blocker / "state.json")  # must not raise

        assert read_projection(blocker / "state.json") is None


class TestTheDatabaseAndTheFolderAgreeing:
    """A file whose bytes ARE the database row's is never drift, whatever the manifest holds.

    Without this the ``refuse`` policy is a one-way trap. The manifest is written only by a
    projection that completes (`write_projection` is reached after the wipe-and-rewrite), and a
    refusal is precisely a projection that does not complete -- so the manifest freezes at the
    moment of the first refusal and every later pass sees the same drift. The two resolutions the
    ERROR message names then behave very differently: deleting the file works, and *adopting* it --
    which is what `check_configs_changes` does on every scheduler reload, and what the API and the
    web UI do -- would never clear the refusal.
    """

    def test_an_adopted_orphan_stops_being_drift(self, tmp_path):
        root = tmp_path / "configs"
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "stray.conf").write_bytes(b"# dropped by hand\n")
        manifest = {}  # the projection wrote nothing, so the file is an orphan

        assert [(drift.path.name, drift.reason) for drift in detect_drift(root, [], manifest)] == [("stray.conf", "orphan")]

        # ... the scheduler reload rescans the folder and saves it as `manual`. Same manifest:
        # a refusal never got to write one.
        adopted = [_config("stray.conf", b"# dropped by hand\n")]

        assert detect_drift(root, adopted, manifest) == []

    def test_an_adopted_edit_stops_being_drift(self, tmp_path):
        root = tmp_path / "configs"
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "cfg.conf").write_bytes(b"# v1\n")
        manifest = _manifest(root, "http/cfg.conf")
        root.joinpath("http", "cfg.conf").write_bytes(b"# EDITED\n")

        assert [drift.reason for drift in detect_drift(root, [_config("cfg.conf", b"# v1\n")], manifest)] == ["modified"]

        # the operator sends the edit through the API: the row now holds the edited bytes
        assert detect_drift(root, [_config("cfg.conf", b"# EDITED\n")], manifest) == []

    def test_a_str_payload_compares_the_same_way(self, tmp_path):
        """The scheduler's API client hands `data` back as `str` on one path and `bytes` on the
        other (`api_client.py` re-encodes); the comparison must not depend on which."""
        root = tmp_path / "configs"
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "cfg.conf").write_bytes(b"# same\n")

        assert detect_drift(root, [_config("cfg.conf", "# same\n")], {}) == []


class TestTheInstancesOwnTreesAreNotJudged:
    """On all-in-one and Linux this folder IS the instance's `/custom_configs` destination.

    `api.lua:683-684` unpacks there, and `pushswap` parks copies *inside* it: `.bw-staging` during
    a push, `.bw-trash` for a stuck entry, `.bw-rescue.<epoch>` kept for seven days. Those sit at
    exactly the depth the projection writes, and `pathlib.Path.glob` -- unlike the shell glob
    `api.lua:792-794` deliberately refuses to rely on -- matches dot-prefixed directories. Judged,
    they are one WARNING per parked file per projection, and under `refuse` a block on every custom
    config change for as long as the rescue tree lives.
    """

    @pytest.mark.parametrize("reserved", [".bw-staging", ".bw-trash", ".bw-rescue.1757000000"])
    def test_a_parked_copy_is_not_an_orphan(self, tmp_path, reserved):
        root = tmp_path / "configs"
        root.joinpath(reserved, "http").mkdir(parents=True)
        root.joinpath(reserved, "http", "parked.conf").write_bytes(b"# parked\n")
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "live.conf").write_bytes(b"# live\n")

        assert [drift.path.name for drift in detect_drift(root, [], {})] == ["live.conf"]

    def test_the_manifest_does_not_record_them_either(self, tmp_path):
        root = tmp_path / "configs"
        root.joinpath(".bw-rescue.1757000000", "http").mkdir(parents=True)
        root.joinpath(".bw-rescue.1757000000", "http", "parked.conf").write_bytes(b"# parked\n")
        root.joinpath("http").mkdir(parents=True)
        root.joinpath("http", "live.conf").write_bytes(b"# live\n")
        state = tmp_path / "state.json"

        write_projection(root, state)

        assert sorted(read_projection(state)) == ["http/live.conf"]


@pytest.mark.parametrize("directory", ["http", "http/app.example.com"])
def test_symlinked_projection_directories_are_not_hashed(tmp_path, directory):
    root = tmp_path / "configs"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.conf").write_bytes(b"private")
    link = root / directory
    link.parent.mkdir(parents=True)
    link.symlink_to(outside, target_is_directory=True)
    assert detect_drift(root, [], {}) == []
    manifest = tmp_path / "manifest.json"
    write_projection(root, manifest)
    assert read_projection(manifest) == {}


@pytest.mark.parametrize("draft", [False, True])
def test_changed_file_without_a_projected_row_warns_about_deletion(tmp_path, draft):
    (tmp_path / "http").mkdir()
    file = tmp_path / "http/gone.conf"
    file.write_bytes(b"original")
    manifest = _manifest(tmp_path, "http/gone.conf")
    file.write_bytes(b"hand edited")
    configs = [_config("gone", b"original", is_draft=True)] if draft else []
    logger = Mock()
    drifts = log_drift(logger, tmp_path, configs, "overwrite", manifest)
    assert len(drifts) == 1
    message = logger.warning.call_args.args[0]
    assert "will be deleted" in message
    assert "will be overwritten" not in message
