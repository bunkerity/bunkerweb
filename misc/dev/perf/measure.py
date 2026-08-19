#!/usr/bin/env python3
"""Report what a UI page render costs, from the outside.

Logs into a running web UI, requests a handful of pages repeatedly and reports the median and
95th percentile wall time, the number of API calls the render made (read from `Server-Timing`,
so it is the UI's own count rather than a guess) and the size of the HTML.

    python3 misc/dev/perf/measure.py --base http://127.0.0.1:7000 --label "20 services"

Deliberately dependency-free: it runs against any environment with nothing to install.
"""

from argparse import ArgumentParser
from http.cookiejar import CookieJar
from json import dumps
from re import search
from statistics import median
from time import perf_counter
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

PAGES = ("/home", "/services", "/instances", "/reports", "/global-settings")


def login(base, username, password):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    page = opener.open(f"{base}/login", timeout=60).read().decode()
    match = search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    if not match:
        raise SystemExit(f"{base}/login served no login form — is the UI still starting, or is the setup wizard pending?")
    body = urlencode({"username": username, "password": password, "csrf_token": match.group(1)}).encode()
    opener.open(
        Request(f"{base}/login", data=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": f"{base}/login"}),
        timeout=60,
    ).read()
    return opener


def measure(opener, base, path, runs):
    opener.open(base + path, timeout=120).read()  # warm-up: the first render pays for the session

    times, calls, api_ms, size, hits = [], None, None, 0, 0
    for _ in range(runs):
        started = perf_counter()
        response = opener.open(base + path, timeout=120)
        payload = response.read()
        times.append((perf_counter() - started) * 1000)

        timing = response.headers.get("Server-Timing", "")
        found = search(r'desc="(\d+) calls"', timing)
        calls = int(found.group(1)) if found else None
        found = search(r"api;dur=([\d.]+)", timing)
        api_ms = float(found.group(1)) if found else None
        # Duplicate GETs answered from the per-request memo (Lot B). A render that shows hits is
        # one where the shared context and the route both asked for the same thing.
        found = search(r'cache;desc="(\d+) hits"', timing)
        hits = int(found.group(1)) if found else 0
        size = len(payload)

    times.sort()
    return {
        "p50": round(median(times), 1),
        "p95": round(times[max(int(len(times) * 0.95) - 1, 0)], 1),
        "api_calls": calls,
        "api_ms": api_ms,
        "memo_hits": hits,
        "html_kb": round(size / 1024, 1),
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:7000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="P@ssw0rd")
    parser.add_argument("--runs", type=int, default=12)
    parser.add_argument("--label", default="", help="Free text recorded alongside the numbers, e.g. the service count")
    parser.add_argument("--pages", nargs="*", default=list(PAGES))
    args = parser.parse_args()

    opener = login(args.base, args.username, args.password)
    print(dumps({"label": args.label, "pages": {path: measure(opener, args.base, path, args.runs) for path in args.pages}}, indent=2))


if __name__ == "__main__":
    main()
