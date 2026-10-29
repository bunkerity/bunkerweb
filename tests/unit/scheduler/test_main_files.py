"""src/scheduler/main.py: the folders the scheduler renders from the database (custom configs, plugins, job caches)."""

import json
import logging
import os
from io import BytesIO
from types import SimpleNamespace

import pytest

from scheduler_fakes import FakeApi


def config(name="a.conf", ctype="http", data=b"server_tokens off;", service_id=None, method="ui", **extra):
    return {"name": name, "type": ctype, "data": data, "service_id": service_id, "method": method, **extra}


@pytest.fixture
def sent(sched_main, monkeypatch):
    calls = []
    monkeypatch.setattr(sched_main, "send_file_to_bunkerweb", lambda path, endpoint, *a, **k: calls.append((path, endpoint)))
    return calls


# --- generate_custom_configs ----------------------------------------------------------------------


def test_custom_configs_are_written_under_their_type_and_service(sched_main, sandbox, fake_sched, sent):
    fake_sched.db.configs = [config("global.conf"), config("svc.conf", "server_http", b"x", "app.example"), config("crs.conf", "modsec_crs", b"y")]
    sched_main.generate_custom_configs(original_path=sandbox.CUSTOM_CONFIGS_PATH)
    base = sandbox.CUSTOM_CONFIGS_PATH
    assert (base / "http" / "global.conf").read_bytes() == b"server_tokens off;"
    assert (base / "server-http" / "app.example" / "svc.conf").read_bytes() == b"x"
    assert (base / "modsec-crs" / "crs.conf").read_bytes() == b"y"
    assert (base / "http" / "global.conf").stat().st_mode & 0o777 == 0o640


def test_the_stem_of_the_name_is_used_so_the_extension_is_never_doubled(sched_main, sandbox, fake_sched, sent):
    sched_main.generate_custom_configs([config("my.rules.conf")], original_path=sandbox.CUSTOM_CONFIGS_PATH)
    assert (sandbox.CUSTOM_CONFIGS_PATH / "http" / "my.rules.conf").is_file()


def test_old_custom_config_files_are_removed_first(sched_main, sandbox, fake_sched, sent):
    base = sandbox.CUSTOM_CONFIGS_PATH
    (base / "http").mkdir()
    (base / "http" / "old.conf").write_text("old")
    (base / "http" / "link.conf").symlink_to(base / "http" / "old.conf")
    (base / "server-http" / "svc").mkdir(parents=True)
    (base / "server-http" / "svc" / "old.conf").write_text("old")
    sched_main.generate_custom_configs([], original_path=base)
    assert list(base.rglob("*.conf")) == []


def test_drafts_and_empty_configs_are_not_written(sched_main, sandbox, fake_sched, sent):
    sched_main.generate_custom_configs([config("draft.conf", is_draft=True), config("empty.conf", data=b"")], original_path=sandbox.CUSTOM_CONFIGS_PATH)
    assert list(sandbox.CUSTOM_CONFIGS_PATH.rglob("*.conf")) == []


def test_incompatible_configs_are_skipped_with_a_warning(sched_main, sandbox, fake_sched, sent, caplog):
    fake_sched.db.compatibility_error = "needs the stream module"
    with caplog.at_level(logging.WARNING):
        sched_main.generate_custom_configs([config("a.conf", service_id="app.example")], original_path=sandbox.CUSTOM_CONFIGS_PATH)
    assert 'Ignoring incompatible custom config "a.conf" for service app.example: needs the stream module' in caplog.text
    assert list(sandbox.CUSTOM_CONFIGS_PATH.rglob("*.conf")) == []


def test_configs_default_to_the_database_and_are_sent_when_instances_exist(sched_main, sandbox, fake_sched, sent):
    fake_sched.db.configs = [config()]
    fake_sched.apis = [FakeApi()]
    sched_main.generate_custom_configs(original_path=sandbox.CUSTOM_CONFIGS_PATH)
    assert (sandbox.CUSTOM_CONFIGS_PATH / "http" / "a.conf").is_file()
    assert sent == [(sandbox.CUSTOM_CONFIGS_PATH, "/custom_configs")]


def test_configs_are_not_sent_without_instances_or_when_asked_not_to(sched_main, sandbox, fake_sched, sent):
    sched_main.generate_custom_configs([config()], original_path=sandbox.CUSTOM_CONFIGS_PATH)
    fake_sched.apis = [FakeApi()]
    sched_main.generate_custom_configs([config()], original_path=sandbox.CUSTOM_CONFIGS_PATH, send=False)
    assert sent == []


def test_a_string_path_is_accepted(sched_main, sandbox, fake_sched, sent):
    sched_main.generate_custom_configs([config()], original_path=str(sandbox.CUSTOM_CONFIGS_PATH), send=False)
    assert (sandbox.CUSTOM_CONFIGS_PATH / "http" / "a.conf").is_file()


def test_a_write_error_is_logged_for_a_ui_config_and_silent_for_a_manual_one(sched_main, sandbox, fake_sched, sent, monkeypatch, caplog):
    def refuse(path, data):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(sched_main, "_write_atomic", refuse)
    with caplog.at_level(logging.ERROR):
        sched_main.generate_custom_configs([config("manual.conf", method="manual")], original_path=sandbox.CUSTOM_CONFIGS_PATH, send=False)
        assert "Error while generating custom configs" not in caplog.text
        sched_main.generate_custom_configs([config("ui.conf", service_id="app")], original_path=sandbox.CUSTOM_CONFIGS_PATH, send=False)
    assert 'Error while generating custom configs "ui.conf" for service app: read-only filesystem' in caplog.text


def test_an_unexpected_error_on_one_config_does_not_stop_the_others(sched_main, sandbox, fake_sched, sent, caplog):
    broken = {"name": "broken.conf", "type": "http", "data": b"x", "service_id": None, "method": "ui"}
    broken["type"] = None
    with caplog.at_level(logging.ERROR):
        sched_main.generate_custom_configs([broken, config("fine.conf")], original_path=sandbox.CUSTOM_CONFIGS_PATH, send=False)
    assert 'Error while generating custom configs "broken.conf"' in caplog.text
    assert (sandbox.CUSTOM_CONFIGS_PATH / "http" / "fine.conf").is_file()


# --- check_configs_changes ------------------------------------------------------------------------


@pytest.fixture
def regenerated(sched_main, monkeypatch):
    calls = []
    monkeypatch.setattr(sched_main, "generate_custom_configs", lambda configs=None, **k: calls.append(configs))
    return calls


def write_conf(sandbox, relative, content="a"):
    path = sandbox.CUSTOM_CONFIGS_PATH / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_no_files_and_no_database_configs_means_no_change(sched_main, sandbox, fake_sched, regenerated):
    assert sched_main.check_configs_changes() is False
    assert regenerated == [[]]


def test_a_hand_written_file_is_saved_as_a_manual_config(sched_main, sandbox, fake_sched, regenerated):
    write_conf(sandbox, "http/mine.conf", "limit_rate 1k;")
    write_conf(sandbox, "server-http/app.example/svc.conf", "x")
    assert sched_main.check_configs_changes() is True
    _, saved, method = [c for c in fake_sched.db.calls if c[0] == "save_custom_configs"][0]
    assert method == "manual"
    assert {(c["exploded"], c["value"]) for c in saved} == {((None, "http", "mine"), "limit_rate 1k;"), (("app.example", "server-http", "svc"), "x")}


def test_files_too_deep_in_the_tree_are_skipped(sched_main, sandbox, fake_sched, regenerated, caplog):
    write_conf(sandbox, "http/a/b/c/too-deep.conf")
    with caplog.at_level(logging.WARNING):
        assert sched_main.check_configs_changes() is False
    assert "is not in the correct path, skipping" in caplog.text


def test_a_file_created_by_env_that_is_not_in_the_database_is_not_saved(sched_main, sandbox, fake_sched, regenerated):
    write_conf(sandbox, "http/env.conf", "# CREATED BY ENV\nx")
    assert sched_main.check_configs_changes() is True
    assert not [c for c in fake_sched.db.calls if c[0] == "save_custom_configs" and c[1]]


def test_a_template_generated_file_is_never_saved_back(sched_main, sandbox, fake_sched, regenerated):
    write_conf(sandbox, "http/tpl.conf")
    fake_sched.db.configs = [{"service_id": None, "name": "tpl", "template": "low", "type": "http"}]
    sched_main.check_configs_changes()
    assert not [c for c in fake_sched.db.calls if c[0] == "save_custom_configs" and c[1]]


def test_generate_false_skips_the_regeneration(sched_main, sandbox, fake_sched, regenerated):
    write_conf(sandbox, "http/mine.conf")
    assert sched_main.check_configs_changes(generate=False) is True
    assert regenerated == []


def test_a_refused_write_returns_none_so_the_folder_is_not_overwritten(sched_main, sandbox, fake_sched, regenerated, caplog):
    write_conf(sandbox, "http/mine.conf")
    fake_sched.db.save_error = "The database is locked"
    with caplog.at_level(logging.ERROR):
        assert sched_main.check_configs_changes() is None
    assert "Couldn't save some manually created custom configs to database: The database is locked" in caplog.text
    assert regenerated == []


def test_per_config_warnings_are_not_a_refused_write(sched_main, sandbox, fake_sched, regenerated):
    write_conf(sandbox, "http/mine.conf")
    fake_sched.db.save_error = "Service ghost not found, please check your config"
    assert sched_main.check_configs_changes() is True
    assert len(regenerated) == 1


def test_an_exception_while_saving_is_a_refused_write(sched_main, sandbox, fake_sched, regenerated, caplog):
    write_conf(sandbox, "http/mine.conf")
    fake_sched.db.save_raises = RuntimeError("conn lost")
    with caplog.at_level(logging.ERROR):
        assert sched_main.check_configs_changes() is None
    assert "Error while saving custom configs to database: conn lost" in caplog.text


def test_a_read_only_database_renders_the_folder_even_though_the_write_was_refused(sched_main, sandbox, fake_sched, regenerated):
    write_conf(sandbox, "http/mine.conf")
    fake_sched.db.readonly = True
    fake_sched.db.save_error = "The database is read-only, the changes will not be saved"
    assert sched_main.check_configs_changes() is True
    assert len(regenerated) == 1


# --- plugins --------------------------------------------------------------------------------------


@pytest.fixture
def validator(sched_main, monkeypatch):
    """Replace the settings-schema validator: a plugin is valid unless its id starts with 'bad'."""
    seen = []

    class Validator:
        def _Configurator__validate_plugin(self, data):
            seen.append(data)
            if data.get("raise"):
                raise ValueError("schema blew up")
            return (not data.get("id", "").startswith("bad"), "missing field")

    monkeypatch.setattr(sched_main, "get_plugin_validator", lambda: Validator())
    return seen


def plugin_dir(base, plugin_id, jobs=True, **plugin_json):
    folder = base / plugin_id
    (folder / "jobs").mkdir(parents=True)
    (folder / "plugin.json").write_text(json.dumps({"id": plugin_id, "name": plugin_id, **plugin_json}))
    if jobs:
        (folder / "jobs" / "job.py").write_text("print(1)")
        # The mode the scheduler gives job scripts: the checksum covers it, so a source tree at 0o644 never matches what was installed.
        (folder / "jobs" / "job.py").chmod(0o750)
    return folder


def row(sched_main, folder, method="ui", **extra):
    """A database row for ``folder`` with the data and checksum the scheduler computes."""
    data = sched_main.create_plugin_tar_gz(folder, arc_root=folder.name)
    return {
        "id": folder.name,
        "name": folder.name,
        "method": method,
        "data": data.getvalue(),
        "checksum": sched_main.bytes_hash(data, algorithm="sha256"),
        **extra,
    }


def test_validate_manual_plugin_accepts_a_valid_plugin(sched_main, validator, tmp_path):
    assert sched_main.validate_manual_plugin({"id": "ok"}, tmp_path / "ok") is True


def test_validate_manual_plugin_rejects_and_logs(sched_main, validator, tmp_path, caplog):
    with caplog.at_level(logging.ERROR):
        assert sched_main.validate_manual_plugin({"id": "bad1"}, tmp_path / "bad1") is False
        assert sched_main.validate_manual_plugin({"id": "x", "raise": 1}, tmp_path / "x") is False
    assert "Ignoring invalid manual plugin bad1: missing field" in caplog.text
    assert "Ignoring invalid manual plugin x: schema blew up" in caplog.text


def test_validate_manual_plugin_can_stay_silent(sched_main, validator, tmp_path, caplog):
    with caplog.at_level(logging.ERROR):
        assert sched_main.validate_manual_plugin({"id": "bad1"}, tmp_path, log_invalid=False) is False
        assert sched_main.validate_manual_plugin({"id": "x", "raise": 1}, tmp_path, log_invalid=False) is False
    assert caplog.text == ""


def test_validate_manual_plugin_does_not_mutate_its_input(sched_main, validator, tmp_path):
    data = {"id": "ok", "settings": {}}
    sched_main.validate_manual_plugin(data, tmp_path)
    assert validator[0] is not data


def test_the_plugin_validator_is_built_once(sched_main, monkeypatch):
    built = []
    monkeypatch.setattr(sched_main, "PLUGIN_VALIDATOR", None)
    monkeypatch.setattr(sched_main, "Configurator", lambda *args: built.append(args) or object())
    first = sched_main.get_plugin_validator()
    assert sched_main.get_plugin_validator() is first
    assert len(built) == 1


def test_plugins_from_the_database_are_extracted_with_executable_jobs(sched_main, sandbox, fake_sched, validator, tmp_path, sent):
    source = plugin_dir(tmp_path / "src", "demo")
    fake_sched.db.plugins = [row(sched_main, source)]
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    job = sandbox.EXTERNAL_PLUGINS_PATH / "demo" / "jobs" / "job.py"
    assert job.read_text() == "print(1)"
    assert job.stat().st_mode & 0o777 == 0o750


def test_an_unchanged_plugin_is_left_in_place(sched_main, sandbox, fake_sched, validator, tmp_path, sent):
    source = plugin_dir(tmp_path / "src", "demo")
    fake_sched.db.plugins = [row(sched_main, source)]
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    job = sandbox.EXTERNAL_PLUGINS_PATH / "demo" / "jobs" / "job.py"
    os.utime(job, (1_000_000, 1_000_000))
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert job.stat().st_mtime == 1_000_000


def test_a_plugin_whose_checksum_changed_is_replaced(sched_main, sandbox, fake_sched, validator, tmp_path, sent):
    source = plugin_dir(tmp_path / "src", "demo")
    fake_sched.db.plugins = [row(sched_main, source)]
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    installed = sandbox.EXTERNAL_PLUGINS_PATH / "demo"
    (installed / "stale").write_text("old")
    fake_sched.db.plugins[0]["checksum"] = "different"
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert not (installed / "stale").exists()
    assert (installed / "jobs" / "job.py").exists()


def test_a_plugin_removed_from_the_database_is_deleted_from_disk(sched_main, sandbox, fake_sched, validator, tmp_path, sent):
    plugin_dir(sandbox.EXTERNAL_PLUGINS_PATH, "gone")
    (sandbox.EXTERNAL_PLUGINS_PATH / "stray.txt").write_text("x")
    fake_sched.db.plugins = [{"id": "other", "name": "other", "method": "ui", "data": None, "checksum": ""}]
    # An api-installed plugin unknown to the database is not preserved: only a manual one with an invalid file is.
    fake_sched.db.plugins.append({"id": "gone", "name": "gone", "method": "ui", "data": None, "checksum": "x"})
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert not (sandbox.EXTERNAL_PLUGINS_PATH / "stray.txt").exists()
    assert not (sandbox.EXTERNAL_PLUGINS_PATH / "gone").exists()


def test_an_invalid_manual_plugin_on_disk_is_preserved(sched_main, sandbox, fake_sched, validator, sent, caplog):
    plugin_dir(sandbox.EXTERNAL_PLUGINS_PATH, "bad-manual")
    with caplog.at_level(logging.WARNING):
        sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert (sandbox.EXTERNAL_PLUGINS_PATH / "bad-manual" / "plugin.json").is_file()
    assert "Preserving invalid manual plugin bad-manual during generation" in caplog.text


def test_a_valid_manual_plugin_unknown_to_the_database_is_removed_to_follow_the_database(sched_main, sandbox, fake_sched, validator, sent):
    plugin_dir(sandbox.EXTERNAL_PLUGINS_PATH, "fine")
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert not (sandbox.EXTERNAL_PLUGINS_PATH / "fine").exists()


def test_a_plugin_json_that_cannot_be_read_is_treated_as_invalid_and_kept(sched_main, sandbox, fake_sched, validator, sent):
    folder = sandbox.EXTERNAL_PLUGINS_PATH / "weird"
    folder.mkdir()
    (folder / "plugin.json").write_text("{broken")
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert (folder / "plugin.json").is_file()


def test_pro_plugins_go_to_the_pro_endpoint(sched_main, sandbox, fake_sched, validator, sent):
    fake_sched.apis = [FakeApi()]
    sched_main.generate_external_plugins(sandbox.PRO_PLUGINS_PATH)
    assert ("get_plugins", "pro", True) in fake_sched.db.calls
    assert sent == [(sandbox.PRO_PLUGINS_PATH, "/pro_plugins")]


def test_external_plugins_go_to_the_plugins_endpoint_unless_send_is_off(sched_main, sandbox, fake_sched, validator, sent):
    fake_sched.apis = [FakeApi()]
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH, send=False)
    assert sent == [(sandbox.EXTERNAL_PLUGINS_PATH, "/plugins")]


def test_missing_plugins_in_the_database_abort_the_generation(sched_main, sandbox, fake_sched, validator, sent):
    fake_sched.db.get_plugins = lambda **k: None
    with pytest.raises(AssertionError, match="Couldn't get plugins from database"):
        sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)


def test_a_corrupt_plugin_archive_is_logged_and_does_not_stop_the_other_plugins(sched_main, sandbox, fake_sched, validator, tmp_path, sent, caplog):
    good = plugin_dir(tmp_path / "src", "good")
    fake_sched.db.plugins = [{"id": "bad", "name": "bad", "method": "ui", "data": b"not a tarball", "checksum": "x"}, row(sched_main, good)]
    with caplog.at_level(logging.ERROR):
        sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert 'Error while generating external plugins "bad"' in caplog.text
    assert (sandbox.EXTERNAL_PLUGINS_PATH / "good" / "plugin.json").is_file()


def test_a_manual_plugin_archive_that_would_overwrite_a_preserved_one_is_skipped(sched_main, sandbox, fake_sched, validator, tmp_path, sent):
    preserved = plugin_dir(sandbox.EXTERNAL_PLUGINS_PATH, "bad-manual")
    (preserved / "mine").write_text("mine")
    source = plugin_dir(tmp_path / "src", "bad-manual")
    fake_sched.db.plugins = [row(sched_main, source, method="manual")]
    sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH)
    assert (preserved / "mine").read_text() == "mine"


# --- generate_caches ------------------------------------------------------------------------------


def cache_row(plugin="plug", job="j", name="a.txt", service_id=None):
    return {"plugin_id": plugin, "job_name": job, "file_name": name, "service_id": service_id}


def test_cache_files_are_restored_from_the_database(sched_main, sandbox, fake_sched):
    fake_sched.db.cache_rows = [cache_row(), cache_row(name="b.txt", service_id="app.example")]
    fake_sched.db.cache_data = {("j", "a.txt", ""): b"alpha", ("j", "b.txt", "app.example"): b"beta"}
    assert sched_main.generate_caches() == set()
    base = sandbox.CACHE_PATH / "plug"
    assert (base / "a.txt").read_bytes() == b"alpha"
    assert (base / "app.example" / "b.txt").read_bytes() == b"beta"
    assert (base / "a.txt").stat().st_mode & 0o777 == 0o640
    assert (base / "app.example").stat().st_mode & 0o777 == 0o750


def test_files_the_database_does_not_know_are_swept_from_a_plugin_cache(sched_main, sandbox, fake_sched):
    base = sandbox.CACHE_PATH / "plug"
    (base / "leftover").mkdir(parents=True)
    (base / "leftover" / "x").write_text("x")
    (base / "stray.txt").write_text("x")
    (base / "dangling").symlink_to(sandbox.root / "nowhere")
    fake_sched.db.cache_rows = [cache_row()]
    fake_sched.db.cache_data = {("j", "a.txt", ""): b"alpha"}
    assert sched_main.generate_caches() == set()
    assert sorted(p.name for p in base.iterdir()) == ["a.txt"]


def test_a_cache_row_without_data_is_reported_as_a_failed_restore(sched_main, sandbox, fake_sched, caplog):
    fake_sched.db.cache_rows = [cache_row(), cache_row(plugin="other", job="k", name="c.txt")]
    fake_sched.db.cache_data = {("k", "c.txt", ""): b"gamma"}
    with caplog.at_level(logging.ERROR):
        failed = sched_main.generate_caches()
    assert failed == {"plug/j"}
    assert "Cache file a.txt not found in database" in caplog.text
    assert (sandbox.CACHE_PATH / "other" / "c.txt").read_bytes() == b"gamma"


def test_a_plugin_with_a_failed_restore_is_not_swept(sched_main, sandbox, fake_sched):
    base = sandbox.CACHE_PATH / "plug"
    base.mkdir(parents=True)
    (base / "precious").write_text("keep")
    fake_sched.db.cache_rows = [cache_row()]
    sched_main.generate_caches()
    assert (base / "precious").read_text() == "keep"


def test_a_path_escaping_the_plugin_cache_is_refused(sched_main, sandbox, fake_sched):
    fake_sched.db.cache_rows = [cache_row(name="../../escape.txt")]
    fake_sched.db.cache_data = {("j", "../../escape.txt", ""): b"x"}
    assert sched_main.generate_caches() == {"plug/j"}
    assert not (sandbox.CACHE_PATH.parent / "escape.txt").exists()


def test_the_mtls_pair_files_are_left_to_their_own_restore(sched_main, sandbox, fake_sched, monkeypatch):
    seen = []
    monkeypatch.setattr(sched_main, "restore_mtls_cache", lambda root, rows: seen.append((root.name, [r["file_name"] for r in rows])) or set())
    fake_sched.db.cache_rows = [cache_row("mtls", "client-cert", "ca.pem"), cache_row("mtls", "client-cert", "crl.pem")]
    assert sched_main.generate_caches() == set()
    assert seen == [("mtls", ["ca.pem", "crl.pem"])]
    assert not (sandbox.CACHE_PATH / "mtls" / "ca.pem").exists()


def test_a_failing_mtls_restore_is_reported_and_blocks_that_plugin(sched_main, sandbox, fake_sched, monkeypatch, caplog):
    monkeypatch.setattr(sched_main, "restore_mtls_cache", lambda root, rows: (_ for _ in ()).throw(ValueError("torn pair")))
    fake_sched.db.cache_rows = [cache_row("mtls", "client-cert", "ca.pem"), cache_row("mtls", "client-cert", "other.bin")]
    fake_sched.db.cache_data = {("client-cert", "other.bin", ""): b"x"}
    with caplog.at_level(logging.ERROR):
        failed = sched_main.generate_caches()
    assert failed == {"mtls/client-cert"}
    assert "Error restoring mTLS cache pairs: torn pair" in caplog.text
    assert not (sandbox.CACHE_PATH / "mtls" / "other.bin").exists()


def test_an_incomplete_crs_plugin_pair_blocks_the_crs_restore(sched_main, sandbox, fake_sched, caplog):
    fake_sched.db.cache_rows = [cache_row("modsecurity", "download-crs-plugins", "crs-plugins.json")]
    with caplog.at_level(logging.ERROR):
        failed = sched_main.generate_caches()
    assert failed == {"modsecurity/download-crs-plugins"}
    assert "Incomplete CRS plugin cache pair" in caplog.text


def test_a_folder_archive_row_is_restored_into_its_directory(sched_main, sandbox, fake_sched):
    import tarfile

    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        payload = b"hello"
        info = tarfile.TarInfo("inner.txt")
        info.size = len(payload)
        tar.addfile(info, BytesIO(payload))
    fake_sched.db.cache_rows = [cache_row(name="bundle.tgz")]
    fake_sched.db.cache_data = {("j", "bundle.tgz", ""): buffer.getvalue()}
    assert sched_main.generate_caches() == set()
    assert (sandbox.CACHE_PATH / "plug" / "inner.txt").read_bytes() == b"hello"


def test_cache_restore_with_nothing_in_the_database_is_a_no_op(sched_main, sandbox, fake_sched):
    assert sched_main.generate_caches() == set()
    assert SimpleNamespace  # nothing restored, nothing swept
