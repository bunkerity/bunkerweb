"""A new mTLS CRL or client CA bundle must drop the cached TLS sessions, or a revoked client keeps resuming (BW-2510).

nginx keeps the session cache zone across a reload, and the session lookup runs on the default server's
SSL_CTX, so no per-server directive can reach it. The zone name therefore carries a hash of every published
service's (name, CA bundle, CRL): any change is a new zone, and an instance with no published mTLS
material keeps the historical name.
"""

import logging
import os
import re
import shutil
from pathlib import Path

import pytest

import Templator as T  # type: ignore  (src/common/gen is on the path, see conftest)
from Configurator import Configurator  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"
DEFAULT_CERT = "/var/cache/bunkerweb/misc/default-server-cert.pem"

CA_A = "-----BEGIN CERTIFICATE-----\nCCCC\n-----END CERTIFICATE-----\n"
CA_B = "-----BEGIN CERTIFICATE-----\nDDDD\n-----END CERTIFICATE-----\n"
CRL_A = "-----BEGIN X509 CRL-----\nAAAA\n-----END X509 CRL-----\n"
CRL_B = "-----BEGIN X509 CRL-----\nBBBB\n-----END X509 CRL-----\n"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect every ``/var/cache/...`` Templator builds from ``sep`` into ``tmp_path``."""
    monkeypatch.setattr(T, "sep", str(tmp_path))
    real_isfile = os.path.isfile
    # The HTTPS block of default-server-http.conf only exists once the default certificate is on disk.
    monkeypatch.setattr(os.path, "isfile", lambda p: True if p == DEFAULT_CERT else real_isfile(p))
    return tmp_path


def publish(sandbox, service, ca=CA_A, crl=None, hidden=False):
    """Publish a service's client CA bundle and optional CRL the way ``client-cert`` does (one directory per service)."""
    path = sandbox / "var" / "cache" / "bunkerweb" / "mtls" / service
    path.mkdir(parents=True, exist_ok=True)
    if ca is not None:
        (path / "ca.pem").write_text(ca)
    if crl is not None:
        (path / "crl.pem").write_text(crl)


def unpublish(sandbox, service):
    shutil.rmtree(sandbox / "var" / "cache" / "bunkerweb" / "mtls" / service)


def render(sandbox, label, **variables):
    plugins = sandbox / "plugins"
    pro_plugins = sandbox / "pro-plugins"
    output = sandbox / f"out-{label}"
    for directory in (plugins, pro_plugins, output):
        directory.mkdir(exist_ok=True)
    variables = {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com", "LISTEN_STREAM": "yes", **variables}
    config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), variables, logging.getLogger("mtls-crl-session")).get_config(None)
    T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()).render()
    return {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*.conf"))}


def zones(tree, stream=False):
    """Every ``(file, zone name)`` the tree declares for the HTTP (or, with ``stream``, the stream) session cache."""
    found = [(name, m.group(1)) for name, text in tree.items() for m in re.finditer(r"^\s*ssl_session_cache\s+shared:(\w+):", text, re.M)]
    return [(name, zone) for name, zone in found if zone.startswith("MozSSLStream") == stream]


HTTP_FILES = ["a.example.com/ssl-certificate-lua.conf", "b.example.com/ssl-certificate-lua.conf", "default-server-http.conf"]


class TestDigest:
    def test_empty_without_any_published_material(self, sandbox):
        assert T.mtls_cache_digest() == ""

    def test_empty_for_a_leftover_service_directory(self, sandbox):
        # A purge leaves an empty directory behind when it removes the published pair.
        publish(sandbox, "a.example.com", ca=None)
        assert T.mtls_cache_digest() == ""

    def test_follows_the_content_only(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        first = T.mtls_cache_digest()
        assert re.fullmatch(r"[0-9a-f]{16}", first)
        assert T.mtls_cache_digest() == first
        publish(sandbox, "a.example.com", crl=CRL_B)
        assert T.mtls_cache_digest() not in ("", first)
        publish(sandbox, "a.example.com", crl=CRL_A)
        assert T.mtls_cache_digest() == first

    def test_a_service_without_a_crl_gets_a_suffix(self, sandbox):
        publish(sandbox, "a.example.com")
        assert re.fullmatch(r"[0-9a-f]{16}", T.mtls_cache_digest())

    def test_a_crl_changes_a_service_that_has_only_a_ca(self, sandbox):
        publish(sandbox, "a.example.com")
        ca_only = T.mtls_cache_digest()
        publish(sandbox, "a.example.com", crl=CRL_A)
        assert T.mtls_cache_digest() != ca_only

    def test_assigning_an_existing_crl_to_a_second_service_changes_it(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        only_a = T.mtls_cache_digest()
        publish(sandbox, "b.example.com", crl=CRL_A)
        both = T.mtls_cache_digest()
        assert both != only_a

    def test_moving_a_crl_to_another_service_changes_it(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        on_a = T.mtls_cache_digest()
        unpublish(sandbox, "a.example.com")
        publish(sandbox, "b.example.com", crl=CRL_A)
        assert T.mtls_cache_digest() not in ("", on_a)

    def test_a_changed_ca_changes_it(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        before = T.mtls_cache_digest()
        publish(sandbox, "a.example.com", ca=CA_B, crl=CRL_A)
        assert T.mtls_cache_digest() not in ("", before)

    def test_removing_a_ca_from_the_bundle_changes_it(self, sandbox):
        publish(sandbox, "a.example.com", ca=CA_A + CA_B, crl=CRL_A)
        before = T.mtls_cache_digest()
        publish(sandbox, "a.example.com", ca=CA_A, crl=CRL_A)
        assert T.mtls_cache_digest() not in ("", before)

    def test_a_missing_root_is_empty(self, sandbox):
        assert not (sandbox / "var" / "cache" / "bunkerweb" / "mtls").exists()
        assert T.mtls_cache_digest() == ""

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
    def test_an_entry_that_cannot_be_inspected_fails_the_generation(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        root = sandbox / "var" / "cache" / "bunkerweb" / "mtls"
        root.chmod(0o444)  # listable, but no entry can be stat'ed: lstat raises PermissionError
        try:
            with pytest.raises(RuntimeError, match=re.escape(str(root / "a.example.com"))):
                T.mtls_cache_digest()
        finally:
            root.chmod(0o755)

    def test_an_entry_that_vanishes_after_the_listing_fails_the_generation(self, sandbox, monkeypatch):
        publish(sandbox, "a.example.com", crl=CRL_A)
        root = sandbox / "var" / "cache" / "bunkerweb" / "mtls"
        real_iterdir = Path.iterdir

        def racing_iterdir(self):
            names = list(real_iterdir(self))
            shutil.rmtree(root / "a.example.com")  # a publication renamed it away after the listing
            return iter(names)

        monkeypatch.setattr(Path, "iterdir", racing_iterdir)
        with pytest.raises(RuntimeError, match=re.escape(str(root / "a.example.com"))):
            T.mtls_cache_digest()

    def test_staging_and_backup_directories_are_ignored(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        before = T.mtls_cache_digest()
        # What StagedDirectory and write_atomic leave beside a live service directory.
        publish(sandbox, ".a.example.com.cache-staging-x1y2z3", ca=CA_B, crl=CRL_B)
        publish(sandbox, ".a.example.com.cache-backup", ca=CA_B, crl=CRL_B)
        (sandbox / "var" / "cache" / "bunkerweb" / "mtls" / ".a.example.com.cache-journal").write_text("{}")
        assert T.mtls_cache_digest() == before

    def test_staging_directories_alone_give_no_suffix(self, sandbox):
        publish(sandbox, ".a.example.com.cache-staging-x1y2z3", ca=CA_B, crl=CRL_B)
        assert T.mtls_cache_digest() == ""

    def test_an_unreadable_published_file_raises_with_its_path(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        crl = sandbox / "var" / "cache" / "bunkerweb" / "mtls" / "a.example.com" / "crl.pem"
        crl.unlink()
        crl.mkdir()  # a read of a directory fails with an OSError whatever the user
        with pytest.raises(RuntimeError, match=re.escape(str(crl))):
            T.mtls_cache_digest()

    def test_an_unreadable_ca_raises_with_its_path(self, sandbox):
        publish(sandbox, "a.example.com")
        ca = sandbox / "var" / "cache" / "bunkerweb" / "mtls" / "a.example.com" / "ca.pem"
        ca.unlink()
        ca.mkdir()
        with pytest.raises(RuntimeError, match=re.escape(str(ca))):
            T.mtls_cache_digest()


class TestRenderedZones:
    def test_no_crl_keeps_the_historical_zone_name(self, sandbox):
        tree = render(sandbox, "none")
        http = zones(tree)
        assert sorted(name for name, _ in http) == HTTP_FILES
        assert {zone for _, zone in http} == {"MozSSL"}
        assert {zone for _, zone in zones(tree, stream=True)} == {"MozSSLStream"}
        assert "shared:MozSSL:10m;" in tree["default-server-http.conf"]

    def test_a_crl_puts_one_digest_in_every_declaration(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        digest = T.mtls_cache_digest()
        tree = render(sandbox, "crl")
        http = zones(tree)
        assert sorted(name for name, _ in http) == HTTP_FILES
        assert {zone for _, zone in http} == {f"MozSSL{digest}"}
        stream = zones(tree, stream=True)
        assert stream and {zone for _, zone in stream} == {f"MozSSLStream{digest}"}

    def test_a_changed_crl_changes_the_zone_without_any_setting_change(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        before = {zone for _, zone in zones(render(sandbox, "before"))}
        publish(sandbox, "a.example.com", crl=CRL_B)
        after = {zone for _, zone in zones(render(sandbox, "after"))}
        again = {zone for _, zone in zones(render(sandbox, "again"))}
        assert len(before) == len(after) == 1 and before != after
        assert after == again

    def test_a_ca_without_a_crl_puts_a_digest_in_every_declaration(self, sandbox):
        publish(sandbox, "a.example.com")
        digest = T.mtls_cache_digest()
        assert digest
        assert {zone for _, zone in zones(render(sandbox, "ca"))} == {f"MozSSL{digest}"}

    def test_removing_all_published_material_restores_the_historical_name(self, sandbox):
        publish(sandbox, "a.example.com", crl=CRL_A)
        unpublish(sandbox, "a.example.com")
        assert {zone for _, zone in zones(render(sandbox, "gone"))} == {"MozSSL"}
