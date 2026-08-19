#!/usr/bin/env python3
"""Create draft services through the API, so the UI can be measured at a realistic size.

    python3 misc/dev/perf/seed.py --api http://127.0.0.1:8888 --count 100

Draft services on purpose: they populate the database, the services page and every per-service
loop in the UI without a BunkerWeb instance having to render or serve any of them.

Idempotent — it counts what is already there and creates the difference.
"""

from argparse import ArgumentParser
from json import dumps, loads
from urllib.request import Request, urlopen

PREFIX = "perf"


def call(api, token, method, path, payload=None):
    request = Request(
        api + path,
        data=dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=300) as response:
        return loads(response.read() or "{}")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8888")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="P@ssw0rd")
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()

    auth = Request(
        f"{args.api}/auth", data=dumps({"username": args.username, "password": args.password}).encode(), headers={"Content-Type": "application/json"}
    )
    with urlopen(auth, timeout=60) as response:
        token = loads(response.read())["token"]

    existing = {service["id"] for service in call(args.api, token, "GET", "/services?limit=500").get("services", [])}
    print(f"{len(existing)} services already, seeding up to {args.count}")

    for index in range(1, args.count + 1):
        name = f"{PREFIX}{index}.example.com"
        if name in existing:
            continue
        call(
            args.api,
            token,
            "POST",
            "/services",
            {
                "server_name": name,
                "variables": {"SERVER_NAME": name, "USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_HOST": "http://app:8080", "REVERSE_PROXY_URL": "/"},
                "is_draft": True,
            },
        )
        if index % 20 == 0:
            print(f"  {index}")

    print("total:", len(call(args.api, token, "GET", "/services?limit=500").get("services", [])))


if __name__ == "__main__":
    main()
