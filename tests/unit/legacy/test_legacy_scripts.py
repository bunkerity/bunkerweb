"""Run dev's standalone test scripts (tests/unit/test_*.py, *.lua, *.sh), one subprocess each.

Each script sets its own sys.path and imports its own `app` package (UI or API), so they cannot share
pytest's interpreter. The root conftest ignores them; this file runs them as they were written.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UNIT = ROOT / "tests" / "unit"
NEEDS_REDIS = {"test_lua_metrics_push_retry.py"}
# strict xfail: a script that starts passing turns the run red, so this set cannot rot.
KNOWN_FAILING = {
    "test_ban_reference.py": "stale against current dev",
    "test_gen_applied_digest.py": "stale against current dev",
    "test_metrics_report_scripts.py": "stale against current dev",
    "test_metrics_ttl_migration.py": "stale against current dev",
    "test_install_sentinel_startup.sh": "stale since fe6bb9bcf: render_temp_config() sits outside the extracted start.sh block",
    "test_letsencrypt_passthrough.lua": "needs resty.openssl (OpenResty)",
    "test_lua_api_digest_lock.lua": "stale against current dev",
    "test_lua_api_reload_serialize.lua": "stale against current dev",
    "test_lua_crowdsec_promotion.lua": "stale against current dev",
    "test_lua_crowdsec_rewritten.lua": "needs ngx.semaphore (OpenResty)",
}


def _cases():
    for pattern in ("test_*.py", "test_*.lua", "test_*.sh", "test_*.cjs"):
        for path in sorted(UNIT.glob(pattern)):
            marks = [pytest.mark.xfail(strict=True, reason=KNOWN_FAILING[path.name])] if path.name in KNOWN_FAILING else []
            yield pytest.param(path, id=path.name, marks=marks)


@pytest.mark.parametrize("path", list(_cases()))
def test_legacy_script(path):
    if path.name in NEEDS_REDIS and not shutil.which("redis-server"):
        pytest.skip("redis-server not installed")
    if path.suffix == ".py":
        # most scripts are unittest modules; a plain script (no unittest) checks itself and sets its exit code.
        # shortcut: substring sniff, misroutes a plain script that only mentions unittest; switch to an AST TestCase check if one appears
        cmd = [sys.executable, "-m", "unittest", "-q", str(path.relative_to(ROOT))] if "unittest" in path.read_text() else [sys.executable, str(path)]
    elif path.suffix == ".cjs":
        node = shutil.which("node")
        if not node:
            pytest.skip("node not installed")
        cmd = [node, "--test", str(path)]
    elif path.suffix == ".lua":
        lua = shutil.which("lua")
        if not lua:
            pytest.skip("lua interpreter not installed")
        cmd = [lua, str(path)]
    else:
        cmd = ["bash", str(path)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"{path.name} exited {proc.returncode}\n{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}"
