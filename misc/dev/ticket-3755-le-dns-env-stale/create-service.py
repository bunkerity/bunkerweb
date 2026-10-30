#!/usr/bin/env python3
"""Create (or delete) a service through the real Web UI, after the container has started.

Posts to the same blueprint the Save button posts to, so the whole UI path runs: form
validation, Config.gen_conf, Database.save_config, the config_changed flags. Scripted only
so the six credential rows are deterministic.

Usage:
    ./create-service.py app2 dns          # RFC2136 DNS-01 with full credentials
    ./create-service.py app4 dns-nocreds  # DNS-01 with no credentials (misconfigured)
    ./create-service.py app2 delete
"""

from sys import argv, exit as sys_exit

from bs4 import BeautifulSoup
from requests import Session

UI = "http://localhost:7355"
USERNAME = "admin"
PASSWORD = "P@ssw0rd"
ZONE = "bwtest.lan"

DNS_CREDENTIALS = (
    "server 10.30.55.53",
    "port 53",
    "name bunkerweb-certbot.",
    "secret QrmNE3WJEYEMVtupVSWlznHxxTyIdR2I4LRiVPGWwpM=",
    "algorithm HMAC-SHA256",
    "sign_query false",
)


def csrf(session: Session, url: str) -> str:
    page = session.get(url)
    page.raise_for_status()
    token = BeautifulSoup(page.text, "html.parser").find("input", {"name": "csrf_token"})
    if not token:
        raise RuntimeError(f"no csrf_token on {url}")
    return token["value"]


def login(session: Session) -> None:
    session.post(
        f"{UI}/login",
        data={"csrf_token": csrf(session, f"{UI}/login"), "username": USERNAME, "password": PASSWORD},
    ).raise_for_status()


def build(name: str, kind: str) -> dict:
    server_name = f"{name}.{ZONE}"
    variables = {
        "SERVER_NAME": server_name,
        "IS_DRAFT": "no",
        "USE_REVERSE_PROXY": "yes",
        "REVERSE_PROXY_URL": "/",
        "REVERSE_PROXY_HOST": "http://app:8080",
        "AUTO_LETS_ENCRYPT": "yes",
        "EMAIL_LETS_ENCRYPT": f"admin@{ZONE}",
        "LETS_ENCRYPT_CHALLENGE": "dns",
        "LETS_ENCRYPT_DNS_PROVIDER": "rfc2136",
        "LETS_ENCRYPT_DNS_PROPAGATION": "10",
    }

    if kind == "dns":
        for index, item in enumerate(DNS_CREDENTIALS):
            suffix = "" if index == 0 else f"_{index}"
            variables[f"LETS_ENCRYPT_DNS_CREDENTIAL_ITEM{suffix}"] = item
            variables[f"LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64{suffix}"] = "no"
    elif kind != "dns-nocreds":
        raise SystemExit(f"unknown kind {kind!r}")

    return variables


def main() -> int:
    if len(argv) != 3:
        raise SystemExit(__doc__)
    name, kind = argv[1], argv[2]
    server_name = f"{name}.{ZONE}"

    session = Session()
    login(session)

    if kind == "delete":
        response = session.post(
            f"{UI}/services/delete",
            # The route does request.form["services"].split(","), so a bare CSV of ids.
            data={"csrf_token": csrf(session, f"{UI}/services"), "services": server_name},
        )
        response.raise_for_status()
        print(f"deleted {server_name} -> HTTP {response.status_code}")
        return 0

    url = f"{UI}/services/new?mode=advanced"
    variables = build(name, kind) | {"csrf_token": csrf(session, url)}
    response = session.post(url, data=variables)
    response.raise_for_status()
    print(f"created {server_name} ({kind}) -> HTTP {response.status_code} {response.url}")
    return 0


if __name__ == "__main__":
    sys_exit(main())
