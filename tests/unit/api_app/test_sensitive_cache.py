"""Sensitive job-cache entries on the REST API: only API admin credentials read their content.

A signed Biscuit holding `cache_read` used to receive every cache row, including per-install
secrets, private keys and DNS-provider credentials, through `GET /cache?with_data=true` and
`GET /cache/{service}/{plugin}/{job}/{file}`. The routes now classify the stored name (convention:
`secret`, `*.secret`, plus the plugin-scoped core mapping) and give the bytes only to a Basic admin
or `API_TOKEN` caller. An admin-issued Biscuit is deliberately not a bypass.

The guard and the Biscuit verification are real, the database is a fake. The byte payloads are
placeholders, never real key material.

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app/test_sensitive_cache.py
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import quote

from bcrypt import gensalt, hashpw
import pytest

from test_biscuit_run_limit import VERSION, _KEYPAIR  # noqa: E402  (bootstrap: keypair, version, key file)

from biscuit_auth import BiscuitBuilder, Fact  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.guard as guard_mod  # noqa: E402
import app.routers.cache as cache_mod  # noqa: E402

ADMIN_TOKEN = "sensitive-cache-admin-token"
BASIC_USER = "sensitive-cache-admin"
BASIC_PASSWORD = "correct"
PLACEHOLDER = b"PLACEHOLDER-BYTES"
ORDINARY_TEXT = b"ordinary text content"
ORDINARY_BINARY = b"\x00\x01\x02binary"


def _token(*perms: tuple[str, str, str], admin: bool = False) -> str:
    builder = BiscuitBuilder(
        "user({user}); time({now}); client_ip({ip}); version({version});",
        {"user": "alice", "now": datetime.now(timezone.utc), "ip": "127.0.0.1", "version": VERSION},
    )
    if admin:
        builder.add_code("admin(true);")
    for rtype, rid, pname in perms:
        builder.add_fact(Fact("api_perm({rtype}, {rid}, {pname})", {"rtype": rtype, "rid": rid, "pname": pname}))
    return builder.build(_KEYPAIR.private_key).to_base64()


READER = _token(("cache", "*", "cache_read"))
DELETER = _token(("cache", "*", "cache_delete"))
ADMIN_BISCUIT = _token(admin=True)
NO_CACHE = _token(("services", "*", "service_read"))

# (stored name, plugin, job): every one of these must be refused to a non-admin.
SENSITIVE = [
    ("secret", "ui_sso", "ui-sso-secret"),
    ("token.secret", "p", "j"),
    ("secret.tgz", "p", "j"),
    ("token.secret.tgz", "p", "j"),
    ("folder:/var/cache/bunkerweb/p/state.secret.tgz", "p", "j"),
    ("key.pem", "customcert", "custom-cert"),
    ("key.pem", "selfsigned", "self-signed"),
    ("default-server-cert.key", "misc", "default-server-cert"),
    ("api-server-cert.key", "jobs", "api-server-cert"),
    ("credentials_0123456789ab.ini", "letsencrypt", "certbot-new"),
    ("folder:/var/cache/bunkerweb/letsencrypt/etc.tgz", "letsencrypt", "certbot-new"),
    ("folder:/var/cache/bunkerweb/letsencrypt/etc.tgz", "letsencrypt", "certbot-renew"),
    ("crowdsec.conf", "crowdsec", "crowdsec-conf"),
    ("folder:/var/tmp/bunkerweb/failover.tgz", "jobs", "failover-backup"),
    ("client-key.pem", "reverseproxy", "trusted-cert"),
    ("client-key.pem", "grpc", "grpc-trusted-cert"),
]

ORDINARY = [
    ("backup.json", "backup", "backup-data"),
    ("SECRET", "p", "j"),
    ("secret.txt", "p", "j"),
    ("folder:/var/cache/bunkerweb/p/secret/ordinary.tgz", "p", "j"),
    ("key.pem", "other", "other-job"),
    ("cert.pem", "customcert", "custom-cert"),
    ("folder:/var/cache/bunkerweb/letsencrypt/etc.tgz", "other", "other-job"),
    ("latest_release.json", "jobs", "update-check"),
    ("client-cert.pem", "reverseproxy", "trusted-cert"),
    ("trusted-ca.pem", "grpc", "grpc-trusted-cert"),
    ("crl.pem", "reverseproxy", "trusted-cert"),
]


def _encode(name: str) -> str:
    """The path token the UI sends for a folder entry: `folder:` kept, `/` written as `_`."""
    return name.replace("/", "_") if name.startswith("folder:") else name


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.byte_fetches = []
        self.list_calls = []
        self.deletes = []
        # True mimics a MariaDB/MySQL `*_general_ci` column: case-insensitive and PAD SPACE (trailing spaces ignored).
        self.ci = False

    def _same(self, left, right):
        return left.casefold().rstrip(" ") == right.casefold().rstrip(" ") if self.ci else left == right

    def get_job_cache_file(self, job_name, file_name, *, service_id="", plugin_id="", with_info=False, with_data=True):
        self.byte_fetches.append((job_name, file_name, plugin_id))
        for row in self.rows:
            if self._same(row["job_name"], job_name) and self._same(row["file_name"], file_name) and self._same(row["plugin_id"], plugin_id):
                # Like the real lookup: the STORED names come back, whatever spelling the caller used.
                return {
                    "data": row["data"],
                    "last_update": None,
                    "checksum": row["checksum"],
                    "file_name": row["file_name"],
                    "job_name": row["job_name"],
                    "plugin_id": row["plugin_id"],
                }
        return None

    def get_jobs_cache_files(self, *, with_data=True, job_name="", plugin_id="", data_job_name=""):
        self.list_calls.append(with_data)
        out = []
        for row in self.rows:
            item = {key: value for key, value in row.items() if with_data or key != "data"}
            out.append(item)
        return out

    def delete_job_cache(self, file_name, *, job_name, service_id=None, plugin_id=""):
        self.deletes.append((file_name, job_name, plugin_id))
        return ""

    def checked_changes(self, **_kwargs):
        return None


def _row(name, plugin, job, data=PLACEHOLDER):
    return {"plugin_id": plugin, "job_name": job, "service_id": None, "file_name": name, "data": data, "last_update": None, "checksum": "sum"}


@pytest.fixture
def db(monkeypatch):
    rows = [_row(name, plugin, job) for name, plugin, job in SENSITIVE + ORDINARY]
    rows.append(_row("notes.txt", "p", "j", ORDINARY_TEXT))
    rows.append(_row("blob.bin", "p", "j", ORDINARY_BINARY))
    fake = FakeDB(rows)
    monkeypatch.setattr(cache_mod, "get_db", lambda: fake)
    database = SimpleNamespace(get_api_user=lambda **_: {"admin": True, "password": hashpw(BASIC_PASSWORD.encode(), gensalt(rounds=4))})
    monkeypatch.setattr(guard_mod, "get_api_db", lambda **_: database)
    monkeypatch.setattr(guard_mod, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    return fake


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(cache_mod.router)
    return TestClient(app, client=("127.0.0.1", 50000))


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _fetch(client, name, plugin, job, *, headers=None, auth=None, download=False):
    url = f"/cache/global/{plugin}/{job}/{quote(_encode(name), safe='')}"
    return client.get(url, params={"download": "true"} if download else None, headers=headers, auth=auth)


@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize("name,plugin,job", SENSITIVE)
def test_cache_read_biscuit_cannot_fetch_sensitive_content(client, db, name, plugin, job, download):
    response = _fetch(client, name, plugin, job, headers=_bearer(READER), download=download)

    assert response.status_code == 403
    assert PLACEHOLDER not in response.content
    assert db.byte_fetches == []


@pytest.mark.parametrize("name,plugin,job", ORDINARY)
def test_ordinary_names_stay_readable_to_a_cache_read_biscuit(client, name, plugin, job):
    response = _fetch(client, name, plugin, job, headers=_bearer(READER))

    assert response.status_code == 200
    assert response.json()["file"]["data"] == PLACEHOLDER.decode()


def test_ordinary_text_and_binary_keep_their_representation(client):
    text = _fetch(client, "notes.txt", "p", "j", headers=_bearer(READER)).json()["file"]
    binary = _fetch(client, "blob.bin", "p", "j", headers=_bearer(READER)).json()["file"]
    download = _fetch(client, "blob.bin", "p", "j", headers=_bearer(READER), download=True)

    assert (text["data"], text["printable"]) == (ORDINARY_TEXT.decode(), True)
    assert (binary["data"], binary["printable"]) == ("Download file to view content", False)
    assert download.status_code == 200 and download.content == ORDINARY_BINARY


def test_a_missing_sensitive_name_is_refused_before_any_lookup(client, db):
    response = _fetch(client, "absent.secret", "p", "j", headers=_bearer(READER))

    assert response.status_code == 403
    assert db.byte_fetches == []
    assert _fetch(client, "absent.txt", "p", "j", headers=_bearer(READER)).status_code == 404


@pytest.mark.parametrize("name,plugin,job", SENSITIVE)
def test_admin_biscuit_is_not_a_bypass(client, db, name, plugin, job):
    assert _fetch(client, name, plugin, job, headers=_bearer(ADMIN_BISCUIT)).status_code == 403
    assert _fetch(client, name, plugin, job, headers=_bearer(ADMIN_BISCUIT), download=True).status_code == 403
    assert db.byte_fetches == []
    assert _fetch(client, "notes.txt", "p", "j", headers=_bearer(ADMIN_BISCUIT)).status_code == 200


@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize("name,plugin,job", SENSITIVE)
@pytest.mark.parametrize("who", ["token", "basic"])
def test_api_admin_credentials_read_sensitive_content(client, name, plugin, job, download, who):
    kwargs = {"headers": _bearer(ADMIN_TOKEN)} if who == "token" else {"auth": (BASIC_USER, BASIC_PASSWORD)}

    response = _fetch(client, name, plugin, job, download=download, **kwargs)

    assert response.status_code == 200
    if download:
        assert response.content == PLACEHOLDER
    else:
        assert response.json()["file"]["data"] == PLACEHOLDER.decode()


def test_listing_omits_sensitive_content_but_keeps_the_metadata(client):
    body = client.get("/cache", params={"with_data": "true"}, headers=_bearer(READER)).json()["cache"]

    by_key = {(item["plugin"], item["job_name"], item["file_name"]): item for item in body}
    for name, plugin, job in SENSITIVE:
        item = by_key[(plugin, job, name)]
        assert "data" not in item and "printable" not in item
        assert item["checksum"] == "sum" and item["service"] == "global"
    for name, plugin, job in ORDINARY:
        assert by_key[(plugin, job, name)]["data"] == PLACEHOLDER.decode()
    assert by_key[("p", "j", "notes.txt")]["printable"] is True
    assert by_key[("p", "j", "blob.bin")]["printable"] is False
    assert PLACEHOLDER.decode() not in "".join(
        str(item.get("data", "")) for item in body if (item["plugin"], item["job_name"], item["file_name"]) in {(p, j, n) for n, p, j in SENSITIVE}
    )


@pytest.mark.parametrize("headers,auth", [(_bearer(ADMIN_TOKEN), None), (None, (BASIC_USER, BASIC_PASSWORD))])
def test_listing_gives_api_admins_the_content(client, headers, auth):
    body = client.get("/cache", params={"with_data": "true"}, headers=headers, auth=auth).json()["cache"]

    assert all(item["data"] and "printable" in item for item in body)


def test_listing_of_an_admin_biscuit_is_redacted_too(client):
    body = client.get("/cache", params={"with_data": "true"}, headers=_bearer(ADMIN_BISCUIT)).json()["cache"]

    assert [item for item in body if item["file_name"] == "secret" and "data" in item] == []


def test_listing_without_data_carries_no_byte_field_for_anyone(client):
    for kwargs in ({"headers": _bearer(READER)}, {"headers": _bearer(ADMIN_TOKEN)}):
        body = client.get("/cache", **kwargs).json()["cache"]
        assert len(body) == len(SENSITIVE) + len(ORDINARY) + 2
        assert all("data" not in item and "printable" not in item for item in body)


def test_authentication_failures_keep_their_original_status(client):
    assert _fetch(client, "secret", "p", "j").status_code == 401
    assert _fetch(client, "secret", "p", "j", headers=_bearer("not-a-token")).status_code == 401
    assert _fetch(client, "secret", "p", "j", headers=_bearer(NO_CACHE)).status_code == 403
    assert client.get("/cache", params={"with_data": "true"}, headers=_bearer(NO_CACHE)).status_code == 403


def test_delete_acl_is_unchanged_for_sensitive_entries(client, db):
    assert client.delete("/cache/global/p/j/token.secret", headers=_bearer(READER)).status_code == 403
    assert db.deletes == []

    single = client.delete("/cache/global/p/j/token.secret", headers=_bearer(DELETER))
    bulk = client.request(
        "DELETE", "/cache", json={"cache_files": [{"service": "global", "plugin": "p", "jobName": "j", "fileName": "secret"}]}, headers=_bearer(DELETER)
    )

    assert single.status_code == 200 and bulk.status_code == 200
    assert db.deletes == [("token.secret", "j", "p"), ("secret", "j", "p")]


def test_a_folder_token_is_normalised_before_classification_and_lookup(client, db):
    stored = "folder:/var/cache/bunkerweb/p/state.secret.tgz"

    assert _fetch(client, stored, "p", "j", headers=_bearer(READER)).status_code == 403
    allowed = _fetch(client, stored, "p", "j", headers=_bearer(ADMIN_TOKEN), download=True)

    assert allowed.status_code == 200 and allowed.content == PLACEHOLDER
    assert db.byte_fetches == [("j", stored, "p")]


# Rework 1: MariaDB/MySQL compare these columns with the database collation (case-insensitive, trailing spaces ignored),
# so a variant the classifier does not recognise can still resolve a stored sensitive row. The route must classify the
# STORED names the lookup returns.
LE_ARCHIVE = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"
# (requested file name, requested plugin, requested job): each resolves a row listed in SENSITIVE under a `_ci` collation.
COLLATION_VARIANTS = [
    ("SECRET", "ui_sso", "ui-sso-secret"),
    ("Secret", "ui_sso", "ui-sso-secret"),
    ("secret ", "ui_sso", "ui-sso-secret"),
    ("TOKEN.SECRET", "p", "j"),
    ("token.SECRET", "p", "j"),
    ("token.secret  ", "p", "j"),
    ("SECRET.TGZ", "p", "j"),
    ("folder:/var/cache/bunkerweb/p/STATE.SECRET.tgz", "p", "j"),
    ("key.pem ", "customcert", "custom-cert"),
    ("key.pem", "customcert ", "custom-cert"),
    ("key.pem", "customcert", "custom-cert "),
    ("KEY.PEM", "CustomCert", "Custom-Cert"),
    ("key.pem", "SelfSigned", "self-signed"),
    ("Default-Server-Cert.KEY", "misc", "default-server-cert"),
    ("api-server-cert.key ", "jobs", "api-server-cert"),
    ("credentials_0123456789ab.ini ", "letsencrypt", "certbot-new"),
    ("CREDENTIALS_0123456789AB.INI", "letsencrypt", "certbot-new"),
    (LE_ARCHIVE + " ", "letsencrypt", "certbot-new"),
    (LE_ARCHIVE.upper().replace("FOLDER:", "folder:"), "letsencrypt", "certbot-renew"),
    ("crowdsec.conf ", "crowdsec", "crowdsec-conf"),
    ("CrowdSec.conf", "crowdsec", "crowdsec-conf"),
    ("crowdsec.conf", "crowdsec", "crowdsec-conf "),
    ("folder:/var/tmp/bunkerweb/failover.tgz", "Jobs", "Failover-Backup"),
    ("folder:/var/tmp/bunkerweb/failover.tgz ", "jobs", "failover-backup"),
    ("Client-Key.PEM", "ReverseProxy", "Trusted-Cert"),
    ("client-key.pem ", "grpc", "grpc-trusted-cert"),
]


@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize("name,plugin,job", COLLATION_VARIANTS)
def test_a_collation_variant_of_a_sensitive_name_gets_no_bytes(client, db, name, plugin, job, download):
    db.ci = True

    reader = _fetch(client, name, plugin, job, headers=_bearer(READER), download=download)
    biscuit_admin = _fetch(client, name, plugin, job, headers=_bearer(ADMIN_BISCUIT), download=download)

    assert reader.status_code == 403 and biscuit_admin.status_code == 403
    assert PLACEHOLDER not in reader.content + biscuit_admin.content


@pytest.mark.parametrize("name,plugin,job", COLLATION_VARIANTS)
def test_api_admin_credentials_still_read_a_collation_variant(client, db, name, plugin, job):
    db.ci = True

    token = _fetch(client, name, plugin, job, headers=_bearer(ADMIN_TOKEN), download=True)
    basic = _fetch(client, name, plugin, job, auth=(BASIC_USER, BASIC_PASSWORD), download=True)

    assert token.status_code == 200 and token.content == PLACEHOLDER
    assert basic.status_code == 200 and basic.content == PLACEHOLDER


@pytest.mark.parametrize(
    "name,plugin,job", [("NOTES.TXT", "P", "J"), ("notes.txt ", "p", "j"), ("BACKUP.JSON", "backup", "backup-data"), ("Cert.PEM", "customcert", "custom-cert")]
)
def test_a_collation_variant_of_an_ordinary_name_stays_readable(client, db, name, plugin, job):
    db.ci = True

    response = _fetch(client, name, plugin, job, headers=_bearer(READER))

    assert response.status_code == 200


@pytest.mark.parametrize("plugin,job", [("reverseproxy", "trusted-cert"), ("grpc", "grpc-trusted-cert")])
def test_a_service_scoped_upstream_client_key_is_admin_only(client, db, plugin, job):
    url = f"/cache/www.example.com/{plugin}/{job}/client-key.pem"

    assert client.get(url, headers=_bearer(READER)).status_code == 403
    assert db.byte_fetches == []
    allowed = client.get(url, params={"download": "true"}, headers=_bearer(ADMIN_TOKEN))
    assert allowed.status_code == 200 and allowed.content == PLACEHOLDER
