r"""A name that ends in a newline must not validate.

Python's `$` matches at the end of the string *and immediately before a trailing newline*, so
`re.match(r"^[\w_-]{1,255}$", "name\n")` is a match. Every name-shaped validator in the UI and the
API was written with `$`, so `"my_config\n"` passed validation and became a filename — which breaks
the line-based directory listing used when pushing configs to instances.

Upstream fixed three of these. This tree has six, and the three upstream never touched include
`_PLUGIN_ID_RX`, which guards a **path-supplied** `plugin_id` on four API endpoints — attacker-
influenced input reaching a filesystem path, not a form typo. Porting the three and calling the
commit done would have left the sharpest one open.

The patterns are read out of the source rather than imported: three of the six live under
`src/api/`, and `fastapi` is not in this suite's requirements. Compiling the pattern text found in
the file is still a behavioural check — it is the real pattern, and it is asserted against real
input, not compared as a string.

**`LOG_RX` is deliberately excluded and must stay that way**, see the last test: it parses nginx log
*lines*, where tolerating the trailing newline is correct. A sweep that "completed the family" by
matching on `$` would break it.
"""

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"

# (file, constant) - every name-shaped validator that guards a value which becomes a path segment.
GUARDS = [
    ("api/app/schemas.py", "NAME_RX"),
    ("api/app/utils.py", "PLUGIN_NAME_RX"),
    ("api/app/routers/plugins.py", "_PLUGIN_ID_RX"),
    ("ui/app/utils.py", "PLUGIN_NAME_RX"),
    ("ui/app/routes/configs.py", "CONFIG_NAME_RX"),
    ("ui/app/routes/utils.py", "PLUGIN_ID_RX"),
]


def _pattern(relative_path, constant):
    """The regex literal assigned to `constant` at the top level of `relative_path`."""
    source = (_SRC / relative_path).read_text(encoding="utf-8")
    match = re.search(rf'^{re.escape(constant)} = (?:re_compile\()?r"([^"]+)"', source, re.M)
    assert match, f'{relative_path}: no top-level `{constant} = r"..."` assignment found'
    return match.group(1)


@pytest.mark.parametrize("relative_path,constant", GUARDS, ids=[f"{p.split('/')[-1]}:{c}" for p, c in GUARDS])
def test_a_name_ending_in_a_newline_is_rejected(relative_path, constant):
    pattern = _pattern(relative_path, constant)
    compiled = re.compile(pattern)

    # The value these guards exist to accept still validates.
    assert compiled.match("my_config") or compiled.match("my.plugin"), f"{constant} rejects an ordinary name"
    # And the one they used to let through does not.
    assert not compiled.match("my_config\n"), f"{constant} still accepts a trailing newline - use \\Z, not $"
    assert not compiled.match("my.plugin\n"), f"{constant} still accepts a trailing newline - use \\Z, not $"


def test_every_guard_actually_moved_off_dollar():
    """Belt and braces: `\\Z` is the fix, and a future edit back to `$` reintroduces the hole.

    The behavioural test above would catch that too; this one names the cause in the failure
    message so nobody has to rediscover why `$` is wrong.
    """
    offenders = [f"{path}:{constant}" for path, constant in GUARDS if _pattern(path, constant).endswith("$")]
    assert not offenders, f"these end in `$`, which matches before a trailing newline: {offenders}"


def test_log_rx_is_left_alone_because_its_input_really_does_end_in_a_newline():
    """The counter-example, pinned so a future sweep does not "finish the job" and break parsing.

    `LOG_RX` matches a line out of an nginx log. Lines end in newlines; `$` tolerating that is the
    correct behaviour here, and `\\Z` would make every complete log line fail to parse. The lesson
    is that the defect is `$` on a *name*, not `$` everywhere.
    """
    pattern = _pattern("ui/app/routes/utils.py", "LOG_RX")
    assert pattern.endswith("$"), "LOG_RX was swept to \\Z - it parses log lines, which end in newlines"
    line = "2026/01/01 00:00:00 [error] 1#1: something failed\n"
    assert re.compile(pattern).match(line), "LOG_RX no longer matches a real log line"
