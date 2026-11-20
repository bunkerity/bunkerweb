#!/usr/bin/env python3
# Print the latest stable (non-prerelease) tag for a GitHub repo using /releases/latest
# Defaults to bunkerity/bunkerweb, override with REPO env var.
#
# Prints an empty line on failure (the caller treats that as "unknown"), but says WHY on stderr:
# the silent version hid an unauthenticated rate limit (60 req/h per IP, shared by every hosted
# runner) behind "Failed to fetch latest stable release" for weeks. Authenticated when the
# workflow hands over GITHUB_TOKEN (1000 req/h per repo), and retried for the transient resets.

import os
import sys
from time import sleep

import httpx

REPO = os.getenv("REPO", "bunkerity/bunkerweb")
API_ROOT = f"https://api.github.com/repos/{REPO}"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "bunkerweb-tests",
}
ATTEMPTS = 3


def request_headers() -> dict:
    headers = dict(HEADERS)
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def latest_stable(client, *, attempts: int = ATTEMPTS, delay: float = 2.0) -> str:
    """Return the latest stable tag without its `v`, or "" after `attempts` failed tries."""
    for attempt in range(1, attempts + 1):
        try:
            r = client.get("/releases/latest")
            r.raise_for_status()
            return (r.json().get("tag_name") or "").removeprefix("v")
        except Exception as e:  # noqa: BLE001 -- every failure class ends the same way: stderr, retry, empty line
            print(f"latest_stable: attempt {attempt}/{attempts} failed: {e!r}", file=sys.stderr)
            if attempt < attempts:
                sleep(delay * attempt)
    return ""


def main() -> int:
    with httpx.Client(base_url=API_ROOT, headers=request_headers(), timeout=httpx.Timeout(15.0), http2=True) as client:
        print(latest_stable(client))
    return 0


if __name__ == "__main__":
    sys.exit(main())
