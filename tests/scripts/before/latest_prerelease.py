#!/usr/bin/env python3
# Fetch the latest prerelease (non-stable) tag for a GitHub repo and print it
# - Defaults to bunkerity/bunkerweb, can override with REPO env var

from contextlib import suppress
import json
import re
import sys
import os
import httpx

# Same directory, run by path from upgrade.sh: sys.path[0] is this directory.
from latest_stable import request_headers  # noqa: E402

REPO = os.getenv("REPO", "bunkerity/bunkerweb")
API_ROOT = f"https://api.github.com/repos/{REPO}"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "bunkerweb-tests",
}


def fetch(path: str) -> str:
    # Use httpx for web requests with a short timeout and HTTP/2 enabled
    # Authenticated when GITHUB_TOKEN is set (see latest_stable.py), and loud on failure: the
    # callers below suppress the exception, so this line is the only trace a rate limit leaves.
    try:
        with httpx.Client(base_url=API_ROOT, headers=request_headers(), timeout=httpx.Timeout(15.0), http2=True) as client:
            r = client.get(path)
            r.raise_for_status()
            return r.text
    except Exception as e:
        print(f"latest_prerelease: GET {path} failed: {e!r}", file=sys.stderr)
        raise


def main() -> int:
    # Try releases endpoint for prereleases
    with suppress(Exception):
        releases = json.loads(fetch("/releases?per_page=100"))
        for rel in releases:
            if rel.get("prerelease") and not rel.get("draft"):
                tag = (rel.get("tag_name") or "").strip()
                if tag.lower() == "testing":
                    continue  # ignore the "testing" version
                print(tag.removeprefix("v"))
                return 0

    # Fallback: scan tags for common pre-release markers
    with suppress(Exception):
        tags = json.loads(fetch("/tags?per_page=100"))
        pattern = re.compile(r"-(rc|alpha|beta|pre|nightly|dev)", re.IGNORECASE)
        for tag in tags:
            name = (tag.get("name") or "").strip()
            if name.lower() == "testing":
                continue  # ignore the "testing" version
            if pattern.search(name):
                print(name.removeprefix("v"))
                return 0

    # Nothing found
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
