"""Unit tests for the certbot-dns-multi provider-translation layer.

Covers ``letsencrypt_providers`` (resolve/translate/format) and the credential parsing in
``letsencrypt_utils.extract_provider`` — the surface that replaced the ~29 per-provider
Pydantic classes when BunkerWeb moved from dedicated ``certbot-dns-*`` plugins to the single
``certbot-dns-multi`` plugin.
"""

from base64 import b64encode
from json import loads as json_loads

import letsencrypt_providers as P
from letsencrypt_utils import LETSENCRYPT_CACHE_PATH, extract_provider

# --------------------------------------------------------------------------- resolve / support


def test_resolve_lego_code_remaps():
    assert P.resolve_lego_code("google") == "gcloud"
    assert P.resolve_lego_code("nsone") == "ns1"
    assert P.resolve_lego_code("gandi") == "gandiv5"
    assert P.resolve_lego_code("rfc2136") == "dnsupdate"
    assert P.resolve_lego_code("domainoffensive") == "dode"


def test_resolve_lego_code_identity_and_unknown():
    assert P.resolve_lego_code("cloudflare") == "cloudflare"  # legacy name == lego code
    assert P.resolve_lego_code("hetzner") == "hetzner"
    assert P.resolve_lego_code("vercel") == "vercel"  # new lego provider, identity
    assert P.resolve_lego_code("totally-bogus") is None
    assert P.resolve_lego_code("") is None


def test_every_legacy_name_resolves_into_the_registry():
    for name, spec in P.LEGACY_ALIASES.items():
        code = P.resolve_lego_code(name)
        assert code == spec["lego_code"]
        assert code in P.LEGO_PROVIDERS, f"{name} -> {code} missing from lego_providers.json"


def test_is_supported_provider():
    assert P.is_supported_provider("cloudflare")
    assert P.is_supported_provider("route53")
    assert P.is_supported_provider("vercel")
    assert not P.is_supported_provider("nope")


def test_is_base64_skip_code():
    assert P.is_base64_skip_code("dnsupdate")
    assert not P.is_base64_skip_code("cloudflare")
    assert not P.is_base64_skip_code(None)


# --------------------------------------------------------------------------- translate_credentials


def test_cloudflare_token():
    prov = P.translate_credentials("cloudflare", "cloudflare", {"cloudflare_api_token": "TKN"})
    assert prov.env == {"CF_DNS_API_TOKEN": "TKN"}
    assert prov.get_formatted_credentials().decode() == "dns_multi_provider = cloudflare\nCF_DNS_API_TOKEN = TKN"
    assert prov.get_file_type() == "ini"


def test_cloudflare_email_key_aliases():
    prov = P.translate_credentials("cloudflare", "cloudflare", {"email": "a@b.c", "api_key": "K"})
    assert prov.env == {"CF_API_EMAIL": "a@b.c", "CF_API_KEY": "K"}


def test_route53_with_region():
    prov = P.translate_credentials(
        "route53",
        "route53",
        {"aws_access_key_id": "AK", "aws_secret_access_key": "SK", "region": "eu-west-1"},
    )
    assert prov.env == {"AWS_ACCESS_KEY_ID": "AK", "AWS_SECRET_ACCESS_KEY": "SK", "AWS_REGION": "eu-west-1"}


def test_route53_missing_secret_returns_none():
    assert P.translate_credentials("route53", "route53", {"aws_access_key_id": "AK"}) is None


def test_rfc2136_port_fold_and_tsig_names():
    prov = P.translate_credentials(
        "dnsupdate",
        "rfc2136",
        {"server": "10.0.0.1", "port": "5353", "name": "key.", "secret": "c2VjcmV0", "algorithm": "hmac-sha256"},
    )
    assert prov.env == {
        "DNSUPDATE_NAMESERVER": "10.0.0.1:5353",
        "DNSUPDATE_TSIG_KEY": "key.",
        "DNSUPDATE_TSIG_SECRET": "c2VjcmV0",
        "DNSUPDATE_TSIG_ALGORITHM": "hmac-sha256",
    }


def test_ionos_combine_prefix_secret():
    prov = P.translate_credentials("ionos", "ionos", {"prefix": "PFX", "secret": "SEC"})
    assert prov.env == {"IONOS_API_KEY": "PFX.SEC"}


def test_ionos_raw_api_key_passthrough():
    prov = P.translate_credentials("ionos", "ionos", {"ionos_api_key": "PFX.SEC"})
    assert prov.env == {"IONOS_API_KEY": "PFX.SEC"}


def test_ovh_endpoint_default_applied():
    prov = P.translate_credentials(
        "ovh",
        "ovh",
        {"application_key": "AK", "application_secret": "AS", "consumer_key": "CK"},
    )
    assert prov.env["OVH_ENDPOINT"] == "ovh-eu"
    assert prov.env["OVH_APPLICATION_KEY"] == "AK"


def test_google_inline_service_account_builds_sidecar():
    items = {
        "type": "service_account",
        "project_id": "proj",
        "private_key_id": "pkid",
        "private_key": "-----BEGIN PRIVATE KEY-----",
        "client_email": "svc@proj.iam.gserviceaccount.com",
        "client_id": "cid",
        "client_x509_cert_url": "https://x",
    }
    prov = P.translate_credentials("gcloud", "google", items)
    assert prov.env.get("GCE_PROJECT") == "proj"
    assert len(prov.sidecars) == 1
    basename, (content, env_key) = next(iter(prov.sidecars.items()))
    assert env_key == "GCE_SERVICE_ACCOUNT_FILE"
    assert basename.startswith("gce_service_account_") and basename.endswith(".json")
    sa = json_loads(content)
    assert sa["project_id"] == "proj"
    assert sa["client_email"] == "svc@proj.iam.gserviceaccount.com"
    # defaults filled from sa_defaults
    assert sa["auth_uri"].startswith("https://accounts.google.com")


def test_google_direct_file_passthrough_no_sidecar():
    prov = P.translate_credentials("gcloud", "google", {"gce_service_account_file": "/run/secrets/sa.json", "project_id": "proj"})
    assert prov.env == {"GCE_SERVICE_ACCOUNT_FILE": "/run/secrets/sa.json", "GCE_PROJECT": "proj"}
    assert not prov.sidecars


def test_new_provider_passthrough_uppercased():
    prov = P.translate_credentials("vercel", "vercel", {"vercel_api_token": "V"})
    assert prov.env == {"VERCEL_API_TOKEN": "V"}


def test_legacy_provider_missing_required_returns_none():
    # domeneshop needs both token and secret
    assert P.translate_credentials("domeneshop", "domeneshop", {"client_token": "T"}) is None


def test_empty_credentials_returns_none():
    assert P.translate_credentials("cloudflare", "cloudflare", {}) is None


def test_formatted_credentials_is_deterministically_sorted():
    a = P.translate_credentials("route53", "route53", {"aws_secret_access_key": "SK", "aws_access_key_id": "AK"})
    b = P.translate_credentials("route53", "route53", {"aws_access_key_id": "AK", "aws_secret_access_key": "SK"})
    assert a.get_formatted_credentials() == b.get_formatted_credentials()


def test_repr_redacts_secrets():
    prov = P.translate_credentials("cloudflare", "cloudflare", {"cloudflare_api_token": "SUPERSECRET"})
    assert "SUPERSECRET" not in repr(prov)
    assert "***" in repr(prov)


# --------------------------------------------------------------------------- data integrity


def test_legacy_aliases_map_to_real_lego_env_vars():
    for name, spec in P.LEGACY_ALIASES.items():
        code = spec["lego_code"]
        known = P._known_env(code)
        for src, dst in spec.get("cred_key_map", {}).items():
            if dst.startswith("__"):
                continue  # internal sentinel consumed by a special handler
            assert dst in known, f"{name}: {src} -> {dst} is not a lego env var of {code}"
        for required in spec.get("required", []):
            assert required in known, f"{name}: required {required} not a lego env var of {code}"


def test_plugin_enum_matches_registry():
    import json
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    plugin = json.loads((repo / "src" / "common" / "core" / "letsencrypt" / "plugin.json").read_text())
    select = set(plugin["settings"]["LETS_ENCRYPT_DNS_PROVIDER"]["select"])
    assert "" in select
    assert P.SUPPORTED_PROVIDER_INPUTS <= select, "every supported provider input must be selectable in the UI"


# --------------------------------------------------------------------------- extract_provider (env parsing)


def _set_item(monkeypatch, idx, value):
    monkeypatch.setenv(f"LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_{idx}", value)


def test_extract_provider_space_separated(monkeypatch):
    _set_item(monkeypatch, 1, "cloudflare_api_token TKN123")
    prov = extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare")
    assert prov is not None
    assert prov.lego_code == "cloudflare"
    assert prov.env == {"CF_DNS_API_TOKEN": "TKN123"}


def test_extract_provider_base64_value_decoded(monkeypatch):
    token = "my-secret-token"
    _set_item(monkeypatch, 1, "cloudflare_api_token " + b64encode(token.encode()).decode())
    prov = extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare", decode_base64=True)
    assert prov.env == {"CF_DNS_API_TOKEN": token}


def test_extract_provider_base64_json_blob(monkeypatch):
    blob = b64encode(b'{"aws_access_key_id": "AK", "aws_secret_access_key": "SK"}').decode()
    _set_item(monkeypatch, 1, blob)
    prov = extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "route53", decode_base64=True)
    assert prov.env == {"AWS_ACCESS_KEY_ID": "AK", "AWS_SECRET_ACCESS_KEY": "SK"}


def test_extract_provider_rfc2136_skips_base64_decode(monkeypatch):
    # A TSIG secret is legitimately base64 and must survive verbatim (dnsupdate is base64-skip).
    secret = "dGhpcy1pcy1iYXNlNjQ="  # valid base64 that should NOT be decoded
    _set_item(monkeypatch, 1, "rfc2136_server 10.0.0.1")
    _set_item(monkeypatch, 2, "rfc2136_name key.")
    _set_item(monkeypatch, 3, f"rfc2136_secret {secret}")
    prov = extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "rfc2136", decode_base64=True)
    assert prov.env["DNSUPDATE_TSIG_SECRET"] == secret


def test_extract_provider_unknown_provider_returns_none(monkeypatch):
    _set_item(monkeypatch, 1, "api_token X")
    assert extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "bogus-provider") is None


def test_extract_provider_no_credentials_returns_none(monkeypatch):
    assert extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "cloudflare") is None


def test_extract_provider_google_sidecar_path_finalized(monkeypatch):
    _set_item(monkeypatch, 1, "project_id proj")
    _set_item(monkeypatch, 2, "private_key -----BEGIN PRIVATE KEY-----")
    _set_item(monkeypatch, 3, "client_email svc@proj.iam.gserviceaccount.com")
    prov = extract_provider("default", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "google")
    assert prov is not None
    # the env var must point at the deterministic cache path so the INI body is stable
    basename = next(iter(prov.sidecars))
    assert prov.env["GCE_SERVICE_ACCOUNT_FILE"] == LETSENCRYPT_CACHE_PATH.joinpath(basename).as_posix()
