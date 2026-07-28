"""Unit tests for the GeoIP job helper shared by geoip-country / geoip-asn / geoip-city.

Covers the two pieces that decide what actually gets downloaded and installed:

* ``resolve_source`` — the implicit priority custom > MaxMind > DB-IP. There is no source
  selector setting, so this function *is* the contract.
* ``unpack`` — DB-IP ships a bare ``.gz``, MaxMind a ``.tar.gz`` holding the database in a
  dated directory, and a custom source may hand over a plain ``.mmdb``.
* ``redact`` — the deprecated MaxMind endpoint carries the licence key in the query string,
  which must never reach the logs.
"""

from datetime import date
from gzip import compress
from io import BytesIO
from tarfile import TarInfo, open as tar_open

import pytest

import geoip_utils as G
from geoip_utils import KINDS, redact, resolve_source, unpack

JULY = date(2026, 7, 15)
KEY = "s3cr3t-licence-key"


def _resolve(kind, today=JULY, **env):
    return resolve_source(kind, env=env, today=today)


# --------------------------------------------------------------------------- priority


def test_no_setting_falls_back_to_dbip():
    source = _resolve("country")
    assert source.provider == "dbip"
    assert source.url == "https://download.db-ip.com/free/dbip-country-lite-2026-07.mmdb.gz"
    assert source.auth is None
    assert source.path == ""


def test_licence_key_switches_to_maxmind():
    source = _resolve("country", MAXMIND_LICENSE_KEY=KEY)
    assert source.provider == "maxmind"
    assert "db-ip.com" not in source.url


def test_custom_beats_maxmind():
    source = _resolve("city", MAXMIND_LICENSE_KEY=KEY, GEOIP_CITY_MMDB="/data/geoip/city.mmdb")
    assert source.provider == "custom"
    assert source.path == "/data/geoip/city.mmdb"
    assert source.url == ""


def test_custom_url_is_kept_as_url_not_path():
    source = _resolve("asn", GEOIP_ASN_MMDB="https://mirror.example.com/asn.mmdb.gz")
    assert source.provider == "custom"
    assert source.url == "https://mirror.example.com/asn.mmdb.gz"
    assert source.path == ""


def test_custom_is_scoped_to_its_own_kind():
    # A custom country database must not drag ASN or city away from their default source.
    env = {"GEOIP_COUNTRY_MMDB": "/data/country.mmdb"}
    assert resolve_source("country", env=env, today=JULY).provider == "custom"
    assert resolve_source("asn", env=env, today=JULY).provider == "dbip"
    assert resolve_source("city", env=env, today=JULY).provider == "dbip"


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_settings_are_ignored(blank):
    source = _resolve("country", GEOIP_COUNTRY_MMDB=blank, MAXMIND_LICENSE_KEY=blank)
    assert source.provider == "dbip"


def test_whitespace_around_values_is_stripped():
    source = _resolve("country", MAXMIND_LICENSE_KEY=f"  {KEY}  ", MAXMIND_ACCOUNT_ID=" 42 ")
    assert source.auth == ("42", KEY)


# --------------------------------------------------------------------------- MaxMind endpoints


def test_account_id_selects_the_basic_auth_endpoint():
    source = _resolve("city", MAXMIND_LICENSE_KEY=KEY, MAXMIND_ACCOUNT_ID="123456")
    assert source.url == "https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz"
    assert source.auth == ("123456", KEY)
    # The key travels in the Authorization header, never in the URL.
    assert KEY not in source.url


def test_key_alone_falls_back_to_the_deprecated_endpoint():
    source = _resolve("city", MAXMIND_LICENSE_KEY=KEY)
    assert source.url.startswith("https://download.maxmind.com/app/geoip_download?")
    assert f"license_key={KEY}" in source.url
    # No auth means the caller knows to warn about the deprecated endpoint.
    assert source.auth is None


@pytest.mark.parametrize(
    ("kind", "edition"),
    [("country", "GeoLite2-Country"), ("asn", "GeoLite2-ASN"), ("city", "GeoLite2-City")],
)
def test_every_kind_maps_to_its_maxmind_edition(kind, edition):
    source = _resolve(kind, MAXMIND_LICENSE_KEY=KEY, MAXMIND_ACCOUNT_ID="1")
    assert f"/databases/{edition}/download" in source.url


@pytest.mark.parametrize(
    ("kind", "slug"),
    [("country", "country"), ("asn", "asn"), ("city", "city")],
)
def test_every_kind_maps_to_its_dbip_edition(kind, slug):
    assert _resolve(kind).url == f"https://download.db-ip.com/free/dbip-{slug}-lite-2026-07.mmdb.gz"


def test_dbip_url_follows_the_month():
    assert "2026-01" in _resolve("country", today=date(2026, 1, 31)).url


def test_redact_hides_the_licence_key():
    url = _resolve("country", MAXMIND_LICENSE_KEY=KEY).url
    assert KEY in url
    assert KEY not in redact(url)
    assert "license_key=***" in redact(url)


def test_redact_leaves_other_urls_alone():
    url = "https://download.db-ip.com/free/dbip-city-lite-2026-07.mmdb.gz"
    assert redact(url) == url


def test_redact_scrubs_a_requests_exception_message():
    """requests embeds the failing URL in its exceptions, key and all.

    This is the path that fires on a wrong or expired key, so redacting only the URLs we
    format ourselves is not enough — it was an actual leak before this test existed.
    """
    url = _resolve("country", MAXMIND_LICENSE_KEY=KEY).url
    message = f"401 Client Error: Unauthorized for url: {url}"
    assert KEY not in redact(message)
    assert "license_key=***" in redact(message)


def test_redact_scrubs_a_traceback():
    url = _resolve("asn", MAXMIND_LICENSE_KEY=KEY).url
    traceback = "\n".join(
        (
            "Traceback (most recent call last):",
            '  File "geoip_utils.py", line 1, in _fetch_payload',
            "    response.raise_for_status()",
            f"requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: {url}",
        )
    )
    assert KEY not in redact(traceback)


def test_redact_stops_at_whitespace_and_keeps_the_rest_of_the_message():
    # The key must be cut without swallowing whatever the exception says after the URL.
    message = f"401 Client Error for url: https://x/?license_key={KEY}&suffix=tar.gz (retrying)"
    scrubbed = redact(message)
    assert KEY not in scrubbed
    assert scrubbed.endswith("(retrying)")
    assert "suffix=tar.gz" in scrubbed


# --------------------------------------------------------------------------- unpacking

MMDB = b"\x00\x01fake mmdb payload" + b"\xab\xcd\xefMaxMind.com"


def _targz(*names):
    """Build a .tar.gz holding one entry per name, like the MaxMind archives."""
    raw = BytesIO()
    with tar_open(fileobj=raw, mode="w") as tar:
        for name in names:
            info = TarInfo(name)
            info.size = len(MMDB)
            tar.addfile(info, BytesIO(MMDB))
    return compress(raw.getvalue())


def test_plain_mmdb_passes_through():
    assert unpack(MMDB) == MMDB


def test_gzip_is_decompressed():
    assert unpack(compress(MMDB)) == MMDB


def test_targz_yields_the_mmdb_member():
    assert unpack(_targz("GeoLite2-City_20260701/GeoLite2-City.mmdb")) == MMDB


def test_targz_ignores_the_sidecar_files_maxmind_ships():
    payload = _targz(
        "GeoLite2-City_20260701/COPYRIGHT.txt",
        "GeoLite2-City_20260701/LICENSE.txt",
        "GeoLite2-City_20260701/GeoLite2-City.mmdb",
    )
    assert unpack(payload) == MMDB


def test_targz_without_a_database_is_rejected():
    with pytest.raises(ValueError, match="no .mmdb member"):
        unpack(_targz("GeoLite2-City_20260701/COPYRIGHT.txt"))


# --------------------------------------------------------------------------- kind registry


def test_city_accepts_only_city_databases():
    # A country database must not silently satisfy the city job.
    assert KINDS["city"].db_types == ("city",)


def test_country_also_accepts_a_city_database():
    # City databases carry country.iso_code, so using one for both is legitimate.
    assert "city" in KINDS["country"].db_types


def test_asn_also_accepts_an_isp_database():
    # GeoIP2-ISP carries the autonomous_system_* fields the ASN lookup reads.
    assert "isp" in KINDS["asn"].db_types


def test_every_kind_has_its_own_cache_file():
    files = {kind.file_name for kind in KINDS.values()}
    assert files == {"country.mmdb", "asn.mmdb", "city.mmdb"}


# --------------------------------------------------------------------------- freshness vs caching


class _FakeJob:
    """Minimal stand-in for utils.jobs.Job — records what run() decided to cache."""

    def __init__(self, tmp_path, cached=None):
        self.job_path = tmp_path
        self._cached = cached
        self.cached_calls = []

    def get_cache(self, *_args, **_kwargs):
        return self._cached

    def cache_file(self, name, path, **kwargs):
        self.cached_calls.append((name, kwargs.get("checksum")))
        return True, "success"


def _bundled_fallback(monkeypatch, tmp_path, cached=None):
    """A bundled /var/tmp database that DB-IP reports as already current."""
    monkeypatch.setattr(G, "TMP_PATH", tmp_path)
    (tmp_path / "country.mmdb").write_bytes(MMDB)
    monkeypatch.setattr(G, "_dbip_is_current", lambda *a, **k: True)
    monkeypatch.setattr(G, "validate", lambda *a, **k: "DBIP-Country-Lite")
    monkeypatch.setattr(G, "_fetch_payload", lambda *a, **k: pytest.fail("must not download when the file is current"))
    return _FakeJob(tmp_path, cached=cached)


def test_current_bundled_database_is_still_cached_on_a_fresh_install(monkeypatch, tmp_path):
    """Regression: the freshness probe must not skip *caching*, only downloading.

    The images bundle a country/asn database under /var/tmp. On a fresh install it is
    usually already the current DB-IP release, so the probe short-circuits — but the
    cache is what gets shipped to the instances. Returning early here left every fresh
    deployment with no database at all, which unit tests could not see and the stack did.
    """
    job = _bundled_fallback(monkeypatch, tmp_path)
    status = G.run("country", _SilentLogger(), job)

    assert job.cached_calls == [("country.mmdb", G.file_hash(tmp_path / "country.mmdb"))]
    assert status == 1  # changed -> instances must reload to pick it up


def test_current_database_already_in_the_cache_short_circuits(monkeypatch, tmp_path):
    # The one case that *may* stop early: the instances already have this exact file.
    job = _bundled_fallback(monkeypatch, tmp_path, cached={"data": MMDB, "checksum": "whatever"})
    status = G.run("country", _SilentLogger(), job)

    assert job.cached_calls == []
    assert status == 0


class _SilentLogger:
    """Swallows the job's progress output — these tests assert on behaviour, not logs."""

    def info(self, *_a, **_k):
        pass

    def warning(self, *_a, **_k):
        pass

    def error(self, *_a, **_k):
        pass

    def debug(self, *_a, **_k):
        pass
