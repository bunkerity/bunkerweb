"""ModSecurity Concurrent audit logging: validation, storage preparation and the hooks that run it (port of dev 4b00bfb15).

``MODSECURITY_SEC_AUDIT_LOG_TYPE=Concurrent`` writes one file per transaction under
``MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR`` and keeps ``MODSECURITY_SEC_AUDIT_LOG`` as the index. A 1.6.15 / 1.6.16
operator who configured it keeps it on the 1.7 upgrade (PO decision D19), so three things must hold:

* ``validate_audit_log_settings`` refuses an invalid candidate BEFORE it is applied, and only looks at the scopes
  that render ModSecurity (dev ``2dc71461f``, tests ``5c58289a0`` / ``c8f806c7d``);
* the instance-side preflight (``modsecurity_audit.py <variables.env>``) creates a missing storage directory as the
  user that runs the nginx worker, never world-writable, and refuses a directory it cannot use;
* every place that starts or reloads nginx runs that preflight first: the container entrypoint (the all-in-one
  image runs the same file), the Linux / FreeBSD ``start.sh``, and the ``reload`` and ``/confs`` endpoints of the
  instance API.
"""

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "src" / "common" / "utils" / "modsecurity_audit.py"

TYPE = "MODSECURITY_SEC_AUDIT_LOG_TYPE"
DIR = "MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR"


def validate_audit_log_settings(*args, **kwargs):
    """Imported per call, so a missing module fails each test on its own instead of the whole file at collection."""
    from modsecurity_audit import validate_audit_log_settings as validate  # type: ignore

    return validate(*args, **kwargs)


class TestConcurrentAuditScopes:
    """Which scopes the validation applies to (dev 5c58289a0 + c8f806c7d, adapted)."""

    def test_global_concurrent_with_per_service_storage_dirs_is_accepted(self):
        """A global Concurrent is allowed when every service supplies its own storage directory."""
        validate_audit_log_settings(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "a.example.com b.example.com",
                TYPE: "Concurrent",
                f"a.example.com_{DIR}": "/var/log/bunkerweb/audit-a",
                f"b.example.com_{DIR}": "/var/log/bunkerweb/audit-b",
            }
        )

    def test_service_with_modsecurity_disabled_does_not_need_a_storage_dir(self):
        """A service with ModSecurity disabled must not be blocked by a missing storage directory."""
        validate_audit_log_settings(
            {"MULTISITE": "yes", "SERVER_NAME": "a.example.com", "a.example.com_USE_MODSECURITY": "no", TYPE: "Concurrent"},
        )

    def test_service_inheriting_concurrent_without_a_storage_dir_is_rejected(self):
        """Only one of two services sets a directory: the other still inherits Concurrent without one, and is named."""
        with pytest.raises(ValueError) as error:
            validate_audit_log_settings(
                {
                    "MULTISITE": "yes",
                    "SERVER_NAME": "a.example.com b.example.com",
                    TYPE: "Concurrent",
                    f"a.example.com_{DIR}": "/var/log/bunkerweb/audit-a",
                }
            )
        assert f"b.example.com_{DIR}" in str(error.value)

    def test_single_site_concurrent_still_requires_a_storage_dir(self):
        """Single-site Concurrent still requires a storage directory."""
        with pytest.raises(ValueError, match="required for Concurrent"):
            validate_audit_log_settings({"MULTISITE": "no", TYPE: "Concurrent"})

    def test_global_crs_mode_still_requires_a_storage_dir(self):
        """Global CRS mode loads one ruleset for the instance, so the GLOBAL scope needs the directory."""
        with pytest.raises(ValueError, match="required for Concurrent"):
            validate_audit_log_settings(
                {"MULTISITE": "yes", "SERVER_NAME": "a.example.com", "USE_MODSECURITY_GLOBAL_CRS": "yes", TYPE: "Concurrent"},
            )

    def test_global_crs_mode_ignores_service_overrides(self):
        """In global CRS mode a service directory cannot stand in for the global one (the README says so)."""
        with pytest.raises(ValueError):
            validate_audit_log_settings(
                {
                    "MULTISITE": "yes",
                    "SERVER_NAME": "a.example.com",
                    "USE_MODSECURITY_GLOBAL_CRS": "yes",
                    TYPE: "Concurrent",
                    f"a.example.com_{DIR}": "/var/log/bunkerweb/audit-a",
                }
            )

    def test_global_crs_mode_with_every_service_off_needs_nothing(self):
        """No HTTP service has ModSecurity on, so the global CRS file is not even loaded."""
        validate_audit_log_settings(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "a.example.com",
                "USE_MODSECURITY_GLOBAL_CRS": "yes",
                "a.example.com_USE_MODSECURITY": "no",
                TYPE: "Concurrent",
            }
        )

    def test_stream_service_renders_no_modsecurity(self):
        """A stream service never renders the HTTP ModSecurity template."""
        validate_audit_log_settings(
            {"MULTISITE": "yes", "SERVER_NAME": "s.example.com", "s.example.com_SERVER_TYPE": "stream", TYPE: "Concurrent"},
        )

    def test_the_reserved_default_server_renders_no_modsecurity(self):
        """``default-server`` is in the roster but its curated plugin subset has no ModSecurity: it needs no directory."""
        validate_audit_log_settings(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "default-server a.example.com",
                TYPE: "Concurrent",
                f"a.example.com_{DIR}": "/var/log/bunkerweb/audit-a",
            }
        )

    def test_unknown_prefix_is_not_a_scope(self):
        """A variable for a service nobody declared is ignored by the Configurator, so it is not validated either."""
        validate_audit_log_settings({"MULTISITE": "yes", "SERVER_NAME": "a.example.com", "ghost.example.com_" + TYPE: "Bogus"})

    def test_storage_dir_is_checked_on_disk_for_an_active_scope(self, tmp_path):
        """An active scope's storage directory is still checked on disk when requested."""
        storage = tmp_path / "audit"
        storage.mkdir()
        config = {"MULTISITE": "no", TYPE: "Concurrent", DIR: str(storage)}
        validate_audit_log_settings(config, check_storage=True)
        storage.rmdir()
        with pytest.raises(ValueError, match="must already exist"):
            validate_audit_log_settings(config, check_storage=True)


class TestValuesAreRefusedBeforeTheyApply:
    @pytest.mark.parametrize("value", ["serial", "Both", "", "Concurrent;"])
    def test_unknown_type(self, value):
        with pytest.raises(ValueError, match="Serial or Concurrent"):
            validate_audit_log_settings({TYPE: value})

    @pytest.mark.parametrize(
        "path",
        ["relative/dir", "/var/log/../etc", "/var/log/bunker web", "/var/log/a;b", "/var/log/a\nb", "/var/log/$HOME", "//double"],
    )
    def test_storage_dir_must_be_a_plain_absolute_path(self, path):
        with pytest.raises(ValueError, match="absolute directory path"):
            validate_audit_log_settings({TYPE: "Concurrent", DIR: path})

    def test_a_bad_path_is_refused_even_while_the_type_is_serial(self):
        """A template may flip Serial to Concurrent after this check, so the path is judged on its own."""
        with pytest.raises(ValueError, match="absolute directory path"):
            validate_audit_log_settings({TYPE: "Serial", DIR: "/var/log/../etc"})

    def test_partial_mode_lets_a_template_supply_the_directory(self):
        validate_audit_log_settings({"MULTISITE": "no", TYPE: "Concurrent"}, partial=True)


class TestOneSixteenConfigurationCarriesOver:
    """The names and defaults of 1.6.16 are the 1.7 ones, so an old configuration validates unchanged."""

    def test_plugin_json_keeps_dev_names_defaults_and_regexes(self):
        import json

        settings = json.loads((ROOT / "src/common/core/modsecurity/plugin.json").read_text(encoding="utf-8"))["settings"]
        assert settings[TYPE]["default"] == "Serial"
        assert settings[TYPE]["regex"] == "^(Serial|Concurrent)$"
        assert settings[TYPE]["select"] == ["Serial", "Concurrent"]
        assert settings[TYPE]["context"] == "multisite"
        assert settings[DIR]["default"] == ""
        assert settings[DIR]["regex"] == "^(?:/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+/?)?$"
        assert settings[DIR]["context"] == "multisite"


def run_preflight(tmp_path, variables: str, *, umask=None):
    env_file = tmp_path / "variables.env"
    env_file.write_text(variables, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(env_file)],
        capture_output=True,
        text=True,
        check=False,
        preexec_fn=(lambda: os.umask(umask)) if umask is not None else None,
    )


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


class TestPreflight:
    """``modsecurity_audit.py <variables.env>``: what every entrypoint runs, as the nginx user, before nginx."""

    def test_creates_a_missing_storage_directory(self, tmp_path):
        storage = tmp_path / "audit"
        result = run_preflight(tmp_path, f"{TYPE}=Concurrent\n{DIR}={storage}\n")
        assert result.returncode == 0, result.stderr
        assert result.stdout == "ModSecurity audit preflight successful\n"
        assert storage.is_dir()
        assert storage.stat().st_uid == os.getuid()

    @pytest.mark.parametrize("umask", [0o022, 0o000, 0o077], ids=["umask-022", "umask-000", "umask-077"])
    def test_created_directories_are_never_world_accessible(self, tmp_path, umask):
        """Audit records carry request headers and bodies. The leaf and every parent it creates are exactly 0750.

        Exactly, not at most: a strict umask would leave 0700 and shut out the group a log shipper reads through.
        """
        storage = tmp_path / "level1" / "level2" / "audit"
        result = run_preflight(tmp_path, f"{TYPE}=Concurrent\n{DIR}={storage}\n", umask=umask)
        assert result.returncode == 0, result.stderr
        for created in (tmp_path / "level1", tmp_path / "level1" / "level2", storage):
            assert mode(created) == 0o750, f"{created} is {oct(mode(created))}"

    def test_an_existing_directory_is_left_alone(self, tmp_path):
        """An operator who provisioned the directory (1.6.16 asked them to) keeps their own mode and content."""
        storage = tmp_path / "audit"
        storage.mkdir()
        storage.chmod(0o770)
        (storage / "keep.txt").write_text("x", encoding="utf-8")
        result = run_preflight(tmp_path, f"{TYPE}=Concurrent\n{DIR}={storage}\n")
        assert result.returncode == 0, result.stderr
        assert mode(storage) == 0o770
        assert (storage / "keep.txt").read_text(encoding="utf-8") == "x"

    def test_serial_creates_nothing(self, tmp_path):
        storage = tmp_path / "audit"
        result = run_preflight(tmp_path, f"{TYPE}=Serial\n{DIR}={storage}\n")
        assert result.returncode == 0, result.stderr
        assert not storage.exists()

    def test_default_configuration_is_serial_and_passes(self, tmp_path):
        assert run_preflight(tmp_path, "SERVER_NAME=\nMULTISITE=no\n").returncode == 0

    def test_concurrent_without_a_directory_is_refused(self, tmp_path):
        result = run_preflight(tmp_path, f"{TYPE}=Concurrent\n")
        assert result.returncode == 1
        assert result.stdout == ""
        assert "ModSecurity audit preflight failed" in result.stderr
        assert DIR in result.stderr

    def test_a_directory_that_cannot_be_created_is_refused(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")
        result = run_preflight(tmp_path, f"{TYPE}=Concurrent\n{DIR}={blocker}/audit\n")
        assert result.returncode == 1
        assert "ModSecurity audit preflight failed" in result.stderr

    @pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory permissions")
    def test_a_directory_the_worker_cannot_write_is_refused(self, tmp_path):
        storage = tmp_path / "audit"
        storage.mkdir()
        storage.chmod(0o500)
        try:
            result = run_preflight(tmp_path, f"{TYPE}=Concurrent\n{DIR}={storage}\n")
        finally:
            storage.chmod(0o700)
        assert result.returncode == 1
        assert "writable/searchable" in result.stderr

    def test_only_active_multisite_scopes_get_a_directory(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        env = (
            f"MULTISITE=yes\nSERVER_NAME=a.example.com b.example.com\n{TYPE}=Concurrent\n"
            f"a.example.com_{DIR}={a}\nb.example.com_{DIR}={b}\nb.example.com_USE_MODSECURITY=no\n"
        )
        result = run_preflight(tmp_path, env)
        assert result.returncode == 0, result.stderr
        assert a.is_dir()
        assert not b.exists()

    def test_a_missing_variables_file_is_a_refusal_not_a_traceback(self, tmp_path):
        result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "absent.env")], capture_output=True, text=True, check=False)
        assert result.returncode == 1
        assert "Traceback" not in result.stderr


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


PREFLIGHT = "modsecurity_audit.py"


class TestEveryStartAndReloadPathRunsThePreflight:
    """Structure, not behaviour: these files need nginx or systemd to run, so the order of the calls is what is pinned."""

    def test_container_entrypoint_checks_before_it_starts_nginx(self):
        text = read("src/bw/entrypoint.sh")
        start = text.index('nginx -g "daemon off;"')
        check = text.rfind(PREFLIGHT, 0, start)
        assert check != -1, "the start path never runs the audit preflight"
        assert "exit 1" in text[check:start], "an invalid audit configuration must refuse to start nginx"
        assert "/etc/nginx/variables.env" in text[check:start]

    def test_container_entrypoint_checks_before_it_reloads_nginx(self):
        text = read("src/bw/entrypoint.sh")
        reload_at = text.index("nginx -s reload")
        check = text.rfind(PREFLIGHT, 0, reload_at)
        assert check != -1 and check > text.index("function trap_reload"), "the HUP reload path never runs the audit preflight"
        assert "return 1" in text[check:reload_at], "an invalid audit configuration must keep the running configuration"

    def test_all_in_one_runs_the_same_entrypoint(self):
        """One edit covers both images: the AIO Dockerfile copies the bw entrypoint and supervisord runs it."""
        assert re.search(r"^COPY src/bw/entrypoint\.sh entrypoint\.sh$", read("src/all-in-one/Dockerfile"), re.M)
        assert "/usr/share/bunkerweb/entrypoint.sh" in read("src/all-in-one/supervisor.d/bunkerweb.ini")

    def test_linux_start_checks_before_it_starts_nginx(self):
        text = read("src/linux/scripts/start.sh")
        start = text.index('log "SYSTEMCTL" "ℹ️" "Starting nginx ..."')
        check = text.rfind(PREFLIGHT, 0, start)
        assert check != -1, "the Linux / FreeBSD start path never runs the audit preflight"
        assert "run_as_nginx" in text[text.rfind("\n", 0, check) : check + len(PREFLIGHT)], "the directory must be created by the nginx user"
        assert "exit 1" in text[check:start]

    def test_linux_reload_checks_before_it_reloads_nginx(self):
        text = read("src/linux/scripts/start.sh")
        reload_def = text.index("function reload()")
        reload_at = text.index("-s reload", reload_def)
        check = text.rfind(PREFLIGHT, reload_def, reload_at)
        assert check != -1, "the Linux / FreeBSD reload path never runs the audit preflight"
        assert "return 1" in text[check:reload_at]

    def test_api_reload_checks_the_live_configuration_first(self):
        text = read("src/bw/lua/bunkerweb/api.lua")
        body = text[text.index("local function reload_locked") :]
        assert body.index("check_audit_storage(") < body.index("test_nginx_conf()")
        assert "VARIABLES_PATH" in body[: body.index("test_nginx_conf()")]

    def test_api_push_checks_the_staged_configuration_before_the_swap(self):
        text = read("src/bw/lua/bunkerweb/api.lua")
        handler = text[text.index('api.global.POST["^/confs$"]') :]
        extract = handler.index("tar xzf")
        check = handler.index("check_audit_storage", extract)
        swap = handler.index("pushswap.swap")
        assert extract < check < swap
        assert "/variables.env" in handler[check : check + 200]
        assert 'destination == "/etc/nginx"' in handler[extract:check]

    @pytest.mark.parametrize("path", ["src/bw/Dockerfile", "src/all-in-one/Dockerfile"])
    def test_images_ship_the_script_the_hooks_call(self, path):
        assert re.search(r"^COPY src/common/utils utils$", read(path), re.M)

    def test_the_script_the_hooks_call_exists_and_needs_only_the_standard_library(self):
        assert SCRIPT.is_file()
        imports = re.findall(r"^(?:from|import) (\w+)", SCRIPT.read_text(encoding="utf-8"), re.M)
        sibling = {"env_file"}
        assert not [name for name in imports if name not in sibling and name not in sys.stdlib_module_names], imports
