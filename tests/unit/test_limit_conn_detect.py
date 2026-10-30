"""Render test: connection limits honour SECURITY_MODE=detect (BW-387).

Run: python3 -B tests/unit/test_limit_conn_detect.py
"""

from pathlib import Path
from sys import exit as sys_exit

from jinja2 import Environment, FileSystemLoader

CONFS = Path(__file__).resolve().parents[2] / "src" / "common" / "core" / "limit" / "confs"
ENV = Environment(loader=FileSystemLoader(CONFS.as_posix()), lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)

BASE = {"LIMIT_CONN_MAX_HTTP1": "1", "LIMIT_CONN_MAX_HTTP2": "2", "LIMIT_CONN_MAX_HTTP3": "3", "LIMIT_CONN_MAX_STREAM": "4"}
TEMPLATES = {
    "server-http/limitconn.conf": ["limit_conn v1ips 1;", "limit_conn v2ips 2;", "limit_conn v3ips 3;"],
    "server-stream/limitconn.conf": ["limit_conn sips 4;"],
}


def render(template: str, security_mode: str, use_limit_conn: str) -> str:
    return ENV.get_template(template).render(**BASE, SECURITY_MODE=security_mode, USE_LIMIT_CONN=use_limit_conn)


def check() -> list:
    failures = []
    for template, lines in TEMPLATES.items():
        for mode in ("detect", "block"):
            out = render(template, mode, "yes")
            for line in lines:
                if line not in out:
                    failures.append(f"{template} {mode}/yes: missing {line!r}")
            expected = "limit_conn_dry_run on;" if mode == "detect" else "limit_conn_dry_run off;"
            if out.count("limit_conn_dry_run") != 1 or expected not in out:
                failures.append(f"{template} {mode}/yes: expected exactly {expected!r}, got {out!r}")
            out = render(template, mode, "no")
            if "limit_conn" in out:
                failures.append(f"{template} {mode}/no: unexpected limit_conn text {out!r}")
        # mixed multisite: each service renders with its own SECURITY_MODE
        a, b = render(template, "detect", "yes"), render(template, "block", "yes")
        if "dry_run on" not in a or "dry_run on" in b:
            failures.append(f"{template} mixed: detect service must get 'on', block service must not")
    return failures


if __name__ == "__main__":
    problems = check()
    for problem in problems:
        print("FAIL:", problem)
    print("FAILED" if problems else "OK")
    sys_exit(1 if problems else 0)
