"""ModSecurity Concurrent audit logging through the real Configurator and Templator (port of dev 4b00bfb15).

Three things are pinned here:

* the rendered ``SecAuditLogType`` / ``SecAuditLogStorageDir`` lines for Serial and Concurrent, in the
  per-service template and in the global CRS one;
* ``http/modsecurity.conf`` loads the global CRS file as soon as ONE http service has ModSecurity on, not only
  when the global ``USE_MODSECURITY`` is (the global-CRS mode validates the global scope against that rule);
* a 1.6.15 / 1.6.16 configuration, written with the names and defaults 1.6 shipped, goes through
  ``Configurator.get_config`` unchanged, and an invalid candidate is refused before anything is rendered.
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"

TYPE = "MODSECURITY_SEC_AUDIT_LOG_TYPE"
DIR = "MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR"
AUDIT_DIR = "/var/log/bunkerweb/audit"
INDEX = "/var/log/bunkerweb/modsec_audit.log"


@pytest.fixture(scope="module")
def render():
    """``render(**variables)`` -> ``{relative path: text}`` of every file the Templator writes, memoised.

    The real Configurator and Templator, with Templator's own jinja whitespace flags (a hand-made Environment
    would make every whitespace assertion below a statement about a string production never emits). The cache
    directory is redirected the way ``render_tree`` does it.
    """
    import Templator as T  # type: ignore
    from Configurator import Configurator  # type: ignore

    with tempfile.TemporaryDirectory() as root:
        sandbox = Path(root)
        original_sep = T.sep
        T.sep = str(sandbox)
        plugins = sandbox / "plugins"
        plugins.mkdir()
        pro_plugins = sandbox / "pro-plugins"
        pro_plugins.mkdir()
        cache = {}

        def _render(**variables):
            key = tuple(sorted(variables.items()))
            if key not in cache:
                config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("audit")).get_config(None)
                output = sandbox / f"out{len(cache)}"
                output.mkdir()
                T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()).render()
                cache[key] = {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*")) if path.is_file()}
            return cache[key]

        try:
            yield _render
        finally:
            T.sep = original_sep


def audit_lines(text: str) -> list:
    """The ``SecAuditLog*`` directives of one rendered rules file, in order."""
    return [line for line in text.splitlines() if re.match(r"SecAuditLog(Type|StorageDir)?\s", line)]


def rules_file(tree: dict, service: str = "") -> str:
    matches = [name for name in tree if name.endswith("server-http/modsecurity-rules.conf.modsec") and (not service or name.startswith(service + "/"))]
    assert len(matches) >= 1, f"no per-service ModSecurity rules file rendered: {sorted(tree)}"
    return tree[matches[0]]


def global_rules_file(tree: dict) -> str:
    """The http-context file. A copy with the request-body rules alone is also rendered in every server block."""
    assert "http/modsecurity-rules-global-crs.conf.modsec" in tree, f"no global CRS rules file rendered: {sorted(tree)}"
    return tree["http/modsecurity-rules-global-crs.conf.modsec"]


class TestSingleSite:
    def test_default_stays_serial_with_no_storage_directive(self, render):
        tree = render(MULTISITE="no", SERVER_NAME="www.example.com")
        assert audit_lines(rules_file(tree)) == ["SecAuditLogType Serial", f"SecAuditLog {INDEX}"]

    def test_concurrent_adds_the_storage_directory_between_type_and_index(self, render):
        tree = render(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Concurrent", DIR: AUDIT_DIR})
        assert audit_lines(rules_file(tree)) == ["SecAuditLogType Concurrent", f"SecAuditLogStorageDir {AUDIT_DIR}", f"SecAuditLog {INDEX}"]

    def test_the_directives_are_at_column_zero_on_their_own_lines(self, render):
        """The template is indented for readability; ``lstrip_blocks`` must leave no stray whitespace or blank line."""
        text = rules_file(render(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Concurrent", DIR: AUDIT_DIR}))
        assert f"SecAuditLogType Concurrent\nSecAuditLogStorageDir {AUDIT_DIR}\nSecAuditLog {INDEX}\n" in text

    def test_serial_ignores_a_leftover_storage_directory(self, render):
        """An operator who switches back to Serial and keeps the directory setting must not get the directive."""
        tree = render(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Serial", DIR: AUDIT_DIR})
        assert audit_lines(rules_file(tree)) == ["SecAuditLogType Serial", f"SecAuditLog {INDEX}"]


class TestMultisite:
    def test_each_service_renders_its_own_writer(self, render):
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{TYPE: "Concurrent", DIR: AUDIT_DIR, f"b.example.com_{TYPE}": "Serial"},
        )
        assert audit_lines(rules_file(tree, "a.example.com")) == ["SecAuditLogType Concurrent", f"SecAuditLogStorageDir {AUDIT_DIR}", f"SecAuditLog {INDEX}"]
        assert audit_lines(rules_file(tree, "b.example.com")) == ["SecAuditLogType Serial", f"SecAuditLog {INDEX}"]

    def test_a_service_directory_overrides_the_global_one(self, render):
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{TYPE: "Concurrent", DIR: AUDIT_DIR, f"b.example.com_{DIR}": "/var/log/bunkerweb/audit-b"},
        )
        assert f"SecAuditLogStorageDir {AUDIT_DIR}\n" in rules_file(tree, "a.example.com")
        assert "SecAuditLogStorageDir /var/log/bunkerweb/audit-b\n" in rules_file(tree, "b.example.com")


class TestGlobalCrs:
    def test_global_file_renders_the_writer_and_the_service_file_renders_nothing(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes", **{TYPE: "Concurrent", DIR: AUDIT_DIR})
        assert audit_lines(global_rules_file(tree)) == ["SecAuditLogType Concurrent", f"SecAuditLogStorageDir {AUDIT_DIR}", f"SecAuditLog {INDEX}"]
        assert audit_lines(rules_file(tree)) == []

    def test_global_file_is_serial_by_default(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes")
        assert audit_lines(global_rules_file(tree)) == ["SecAuditLogType Serial", f"SecAuditLog {INDEX}"]

    def test_global_crs_loads_when_one_service_has_modsecurity_on(self, render):
        """Global ``USE_MODSECURITY=no`` with one service ``yes``: the old test (global value only) never loaded it."""
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            USE_MODSECURITY_GLOBAL_CRS="yes",
            USE_MODSECURITY="no",
            **{"a.example.com_USE_MODSECURITY": "yes"},
        )
        assert "modsecurity on;" in tree["http/modsecurity.conf"]
        assert "modsecurity-rules-global-crs.conf.modsec" in tree["http/modsecurity.conf"]

    def test_global_crs_stays_off_when_no_http_service_has_modsecurity_on(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes", USE_MODSECURITY="no")
        assert "modsecurity on;" not in tree["http/modsecurity.conf"]

    def test_global_crs_off_loads_nothing_in_the_http_context(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="no")
        assert "modsecurity on;" not in tree["http/modsecurity.conf"]


class TestOneSixteenConfigurationCarriesOver:
    """The settings are validated through the real ``Configurator.get_config`` with a 1.6.16-style environment."""

    def config(self, **variables):
        from Configurator import Configurator  # type: ignore

        plugins = Path(tempfile.mkdtemp())
        return Configurator(str(SETTINGS), str(CORE), str(plugins), str(plugins), dict(variables), logging.getLogger("audit")).get_config(None)

    def test_a_valid_1_6_16_environment_is_kept_unchanged(self):
        config = self.config(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{
                TYPE: "Concurrent",
                DIR: AUDIT_DIR,
                f"b.example.com_{TYPE}": "Serial",
                "MODSECURITY_SEC_AUDIT_LOG": "/var/log/bunkerweb/modsec_audit.log",
            },
        )
        assert config[TYPE] == "Concurrent"
        assert config[DIR] == AUDIT_DIR
        assert config[f"b.example.com_{TYPE}"] == "Serial"
        assert config[f"a.example.com_{TYPE}"] == "Concurrent"
        assert config[f"a.example.com_{DIR}"] == AUDIT_DIR

    def test_the_defaults_are_the_1_6_16_ones(self):
        config = self.config(MULTISITE="no", SERVER_NAME="www.example.com")
        assert (config[TYPE], config[DIR]) == ("Serial", "")

    def test_concurrent_without_a_directory_is_refused_before_anything_renders(self):
        with pytest.raises(ValueError, match="required for Concurrent"):
            self.config(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Concurrent"})

    def test_a_bad_type_is_refused(self):
        """The plugin.json regex would drop it with a warning and fall back to Serial; the validator refuses instead."""
        with pytest.raises(ValueError, match="Serial or Concurrent"):
            self.config(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Parallel"})

    def test_a_traversal_path_is_refused(self):
        with pytest.raises(ValueError, match="absolute directory path"):
            self.config(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Concurrent", DIR: "/var/log/../etc"})

    def test_only_one_of_two_services_having_a_directory_is_refused(self):
        with pytest.raises(ValueError, match=re.escape(f"b.example.com_{DIR}")):
            self.config(
                MULTISITE="yes",
                SERVER_NAME="a.example.com b.example.com",
                **{TYPE: "Concurrent", f"a.example.com_{DIR}": AUDIT_DIR},
            )


class TestTheDatabasePathIsValidatedToo:
    def test_main_validates_before_it_removes_the_working_files(self):
        """The scheduler renders from the database and never builds a Configurator: ``main.py`` is its only gate."""
        text = (ROOT / "src" / "common" / "gen" / "main.py").read_text(encoding="utf-8")
        check = text.index("validate_audit_log_settings(")
        assert check < text.index('LOGGER.info("Removing old files ...")')
        assert "from modsecurity_audit import validate_audit_log_settings" in text


class TestTheGeneratedVariablesFilePassesTheInstancePreflight:
    """What the generator writes is what the instance preflight reads: the two halves must agree on the format."""

    SCRIPT = ROOT / "src" / "common" / "utils" / "modsecurity_audit.py"

    def preflight(self, tmp_path, variables_env: str):
        env_file = tmp_path / "variables.env"
        env_file.write_text(variables_env, encoding="utf-8")
        return subprocess.run([sys.executable, str(self.SCRIPT), str(env_file)], capture_output=True, text=True, check=False)

    def test_concurrent_creates_the_directory_named_in_the_rendered_file(self, render, tmp_path):
        storage = tmp_path / "audit"
        tree = render(MULTISITE="no", SERVER_NAME="www.example.com", **{TYPE: "Concurrent", DIR: str(storage)})
        result = self.preflight(tmp_path, tree["variables.env"])
        assert result.returncode == 0, result.stderr
        assert storage.is_dir()
        assert oct(storage.stat().st_mode & 0o777) == "0o750"
        assert storage.stat().st_uid == os.getuid()

    def test_multisite_creates_each_service_directory(self, render, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        tree = render(
            MULTISITE="yes",
            SERVER_NAME="a.example.com b.example.com",
            **{TYPE: "Concurrent", f"a.example.com_{DIR}": str(a), f"b.example.com_{DIR}": str(b)},
        )
        result = self.preflight(tmp_path, tree["variables.env"])
        assert result.returncode == 0, result.stderr
        assert a.is_dir() and b.is_dir()

    def test_the_default_render_is_serial_and_creates_nothing(self, render, tmp_path):
        tree = render(MULTISITE="no", SERVER_NAME="www.example.com")
        assert self.preflight(tmp_path, tree["variables.env"]).returncode == 0
        assert sorted(path.name for path in tmp_path.iterdir()) == ["variables.env"]
