#!/usr/bin/env python3
# Print the latest stable (non-prerelease) tag for a GitHub repo using /releases/latest
# Defaults to bunkerity/bunkerweb, override with REPO env var

import os
import sys
import httpx

REPO = os.getenv("REPO", "bunkerity/bunkerweb")
API_ROOT = f"https://api.github.com/repos/{REPO}"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "bunkerweb-tests",
}


def main() -> int:
    try:
        with httpx.Client(base_url=API_ROOT, headers=HEADERS, timeout=httpx.Timeout(15.0), http2=True) as client:
            r = client.get("/releases/latest")
            r.raise_for_status()
            data = r.json()
            tag = data.get("tag_name") or ""
            print(tag.removeprefix("v"))
            return 0
    except Exception:
        # Keep it simple: print nothing on failure
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
