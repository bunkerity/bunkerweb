"""A remediation the plugin served itself is a report, whatever status it ended on.

``metrics:log()`` buffers a record only when a plugin set a reason, and ``is_report()`` then
decides which of those records the Reports page shows. Its test was "4xx, or detect, or a stream
session" — which silently drops every remediation that answers the request *instead of* the
origin rather than blocking it. CrowdSec 1.8's AppSec bot-detection challenge is exactly that:
the challenge page is served with the status AppSec chose (a 200) and the origin is never
reached, so the row was written with ``reason = "crowdsec"`` and displayed nowhere.

Both halves of the filter are pinned here because they are two implementations of one rule:
``is_report()`` gates the live in-memory buffer an instance serves from ``/metrics/requests``,
``_report_clause()`` gates the same records again once the scheduler has persisted them. A
widening applied to only one of them makes a report appear and then vanish (or the reverse) as
the buffer rolls over — which is worse than either behaviour on its own.

The Lua half runs the *shipped* ``is_report`` through the ``lua`` binary rather than asserting on
its source text: what matters is the verdict for a given record, not the spelling of the
condition.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

SOURCE = METRICS_LUA.read_text(encoding="utf-8")


def _extract_function(name: str) -> str:
    match = re.search(rf"^local function {name}\(.*?^end$", SOURCE, re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _is_report(**record) -> bool:
    """Run the shipped is_report() against one record and return its verdict."""
    assert LUA is not None
    fields = []
    for key, value in record.items():
        if value is None:
            continue
        literal = f"[==[{value}]==]" if isinstance(value, str) else str(value)
        fields.append(f"{key} = {literal}")
    # is_report() is spliced on its own, exactly as test_metrics_stream.py's own harness does
    # it: the function must stay free of module upvalues or it is a nil index here.
    script = "\n".join(
        [
            _extract_function("is_report"),
            "print(tostring(is_report({ " + ", ".join(fields) + " })))",
        ]
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    out = result.stdout.strip()
    assert out in ("true", "false"), out
    return out == "true"


@needs_lua
class TestIsReport:
    def test_a_served_crowdsec_challenge_is_a_report(self):
        """The whole point of the lane: a 200 that a security plugin answered itself."""
        assert _is_report(protocol="http", status=200, reason="crowdsec", security_mode="block")

    def test_a_crowdsec_block_is_still_a_report(self):
        assert _is_report(protocol="http", status=403, reason="crowdsec", security_mode="block")

    def test_a_served_antibot_challenge_is_a_report(self):
        """Antibot answers the request itself on ngx.OK and the content phase renders the
        challenge page with a 200 — the same shape as CrowdSec's served challenge, and invisible
        for the same reason before this arm."""
        assert _is_report(protocol="http", status=200, reason="antibot", security_mode="block")

    def test_a_workflows_redirect_is_a_report(self):
        """The redirect action exits through ngx_redirect() with a 3xx: neither 4xx, nor detect,
        nor a stream session, so the row was written with a reason and shown nowhere."""
        assert _is_report(protocol="http", status=302, reason="workflows", security_mode="block")

    def test_the_allowlist_is_case_insensitive(self):
        """The reason is compared lowercased on both halves — case-sensitively on PostgreSQL and
        not on MariaDB otherwise. Every producer writes a lowercase plugin id today; this pins
        that the two engines cannot start disagreeing."""
        assert _is_report(protocol="http", status=200, reason="AntiBot", security_mode="block")

    def test_an_ordinary_3xx_row_is_not_dragged_in(self):
        """The redirect arm is keyed on the reason too: an ordinary 302 a future plugin records
        for some other purpose must stay out."""
        assert not _is_report(protocol="http", status=302, reason="blacklist", security_mode="block")

    def test_an_ordinary_2xx_row_is_not_dragged_in(self):
        """The arm is keyed on the reason, not on a widened status range — a 200 recorded by any
        other plugin must stay out, which is what the range would have broken."""
        assert not _is_report(protocol="http", status=200, reason="blacklist", security_mode="block")

    def test_the_4xx_arm_is_untouched(self):
        assert _is_report(protocol="http", status=403, reason="blacklist", security_mode="block")

    def test_the_detect_arm_is_untouched(self):
        assert _is_report(protocol="http", status=200, reason="blacklist", security_mode="detect")

    def test_the_stream_arm_is_untouched(self):
        assert _is_report(protocol="tcp", status=444, reason="blacklist", security_mode="block")

    def test_a_reason_that_is_not_a_string_does_not_abort_the_listing(self):
        """Records are decoded straight out of the shared dict. ``string.lower()`` on a table
        raises, and is_report() runs inside the loop that builds the whole Reports response — one
        malformed record would empty the page rather than drop a row."""
        assert LUA is not None
        script = "\n".join(
            [
                _extract_function("is_report"),
                'print(tostring(is_report({ protocol = "http", status = 200, reason = {} })))',
            ]
        )
        result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
        assert result.returncode == 0, f"is_report() raised on a non-string reason:\n{result.stderr}"
        assert result.stdout.strip() == "false"

    def test_a_record_with_no_reason_is_not_a_report(self):
        """is_report() is also fed records straight out of the shared dict; indexing the
        allowlist with a nil key must not raise."""
        assert not _is_report(protocol="http", status=200, security_mode="block")


class TestTheTwoHalvesAgree:
    def test_the_lua_and_python_allowlists_name_the_same_reasons(self):
        """The two filters run over the same records at two different moments. Drifting them
        makes a report appear in the live buffer and disappear once persisted.

        The Lua side spells its reasons inline (see ``is_report``); the Python side keeps them in
        a tuple. Both are read from the source text rather than imported: ``db_methods/metrics.py``
        is a package module with relative imports and importing it here would drag in the whole DB
        layer for one tuple."""
        lua_reasons = set(re.findall(r'reason == "([^"]+)"', _extract_function("is_report")))
        # Without this, dropping the inline form on one side and the string literals on the other
        # leaves two empty sets, which compare equal and pass.
        assert lua_reasons, "is_report() no longer spells its reasons inline"
        python_source = (ROOT / "src" / "common" / "db" / "db_methods" / "metrics.py").read_text(encoding="utf-8")
        match = re.search(r"^_SELF_SERVED_REASONS = \((.*?)\)$", python_source, re.S | re.M)
        assert match, "_SELF_SERVED_REASONS is gone from db_methods/metrics.py"
        python_reasons = set(re.findall(r'"([^"]+)"', match.group(1)))
        assert lua_reasons == python_reasons
