r"""A name that ends in a newline must not validate.

Python's `$` matches at the end of the string *and immediately before a trailing newline*, so
`re.match(r"^[\w_-]{1,255}$", "name\n")` is a match. Every name-shaped validator in the UI and the
API was written with `$`, so `"my_config\n"` passed validation and became a filename — which breaks
the line-based directory listing used when pushing configs to instances.

Upstream fixed three of these. This tree has ten, and the six upstream never touched include
`_PLUGIN_ID_RX`, which guards a **path-supplied** `plugin_id` on four API endpoints — attacker-
influenced input reaching a filesystem path, not a form typo. Porting the three and calling the
commit done would have left the sharpest one open.

The last three were found by widening the search past the shape of the first six. That matters,
because they are not all the same defect and the sweep that found the six could not have found
them:

* `REVERSE_PROXY_PATH` is a **validator** like the six, and the sharpest of the nine —
  `setup.py:226` writes the *original* string into `REVERSE_PROXY_HOST`, which is rendered into an
  nginx `proxy_pass`, so the newline is carried through verbatim.
* `CUSTOM_CONF_RX` and `FILE_SETTING_NAME_RX` are **extractors**, not validators. `.` never
  matches a newline, so the captured name never contains it. What `$` buys there is that the
  dirty key matches *at all*, and then derives the same config key as the clean one — two form
  fields silently aliased onto one config. Lesser, still wrong, zero cost to close.

The tenth was found afterwards, by asking where else the same constant lives: `CUSTOM_CONF_RX` is
declared **twice**, in `src/ui/app/routes/utils.py` and in `src/common/gen/save_config.py`, and the
two had already drifted — the UI copy was anchored and the generation copy was not. Both are covered
here deliberately. Deduplicating them crosses the UI/gen boundary and is deferred; until then this
test is the only thing that notices when one copy is fixed and the other is not.

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


# (file, constant, a value that must still match, the same value with a trailing newline).
# Separate from GUARDS because these are not all `^[\w_-]+$` name validators: one takes a URL and
# two are extractors whose input is a form key, so each needs its own sample.
WIDER_GUARDS = [
    ("ui/app/routes/utils.py", "REVERSE_PROXY_PATH", "https://ui.example.com:8080"),
    ("ui/app/routes/utils.py", "CUSTOM_CONF_RX", "CUSTOM_CONF_HTTP_my_conf"),
    ("ui/app/routes/utils.py", "FILE_SETTING_NAME_RX", "MY_SETTING__FILE_NAME_1"),
    # The tenth: the same regex, a second time, in config generation rather than the UI. Its input
    # is an environment key rather than a form field, and it is listed here rather than in its own
    # test on purpose -- one guard over both homes is what keeps the copies from drifting again.
    ("common/gen/save_config.py", "CUSTOM_CONF_RX", "CUSTOM_CONF_HTTP_my_conf"),
]


def _pattern(relative_path, constant):
    """The regex literal assigned to `constant` at the top level of `relative_path`."""
    source = (_SRC / relative_path).read_text(encoding="utf-8")
    # `\s*` after the opening paren: `CUSTOM_CONF_RX` is long enough that black wraps it onto its
    # own line, and a pattern that only matched the single-line form would silently skip it.
    match = re.search(rf'^{re.escape(constant)} = (?:re_compile\(\s*)?r"([^"]+)"', source, re.M)
    assert match, f'{relative_path}: no top-level `{constant} = r"..."` assignment found'
    return match.group(1)


def test_the_guard_lists_are_not_empty():
    """Anti-vacuity. Mutant D on this file emptied `GUARDS`: the parametrized test skipped and
    `test_every_guard_actually_moved_off_dollar` iterated nothing and **passed** -- 7 passed, 0
    failed, every real assertion gone. The dollar-sweep test is the dangerous one, because a
    vacuous `all()` over an empty list is indistinguishable from a clean bill of health."""
    # A FLOOR, not an exact count. I first wrote `== 3` for WIDER_GUARDS from memory and it went
    # red -- because @merge had added a fourth entry, the `save_config.py` twin of `CUSTOM_CONF_RX`
    # that this lane reported and did not own. Another lane widening a shared guard is the system
    # working; an exact count would have fought it. A shrink still fails.
    assert len(GUARDS) >= 6, f"the six approved name validators shrank to {len(GUARDS)}"
    assert len(WIDER_GUARDS) >= 3, f"the widened guards shrank to {len(WIDER_GUARDS)}"
    # And each one must still resolve to a real pattern, so emptying the FILES is caught too.
    for path, constant in GUARDS + [(p, c) for p, c, _ in WIDER_GUARDS]:
        assert _pattern(path, constant), f"{path}:{constant} no longer resolves"


@pytest.mark.parametrize("relative_path,constant", GUARDS, ids=[f"{p.split('/')[-1]}:{c}" for p, c in GUARDS])
def test_a_name_ending_in_a_newline_is_rejected(relative_path, constant):
    pattern = _pattern(relative_path, constant)
    compiled = re.compile(pattern)

    # The value these guards exist to accept still validates.
    assert compiled.match("my_config") or compiled.match("my.plugin"), f"{constant} rejects an ordinary name"
    # And the one they used to let through does not.
    assert not compiled.match("my_config\n"), f"{constant} still accepts a trailing newline - use \\Z, not $"
    assert not compiled.match("my.plugin\n"), f"{constant} still accepts a trailing newline - use \\Z, not $"


@pytest.mark.parametrize("relative_path,constant,good", WIDER_GUARDS, ids=[c for _, c, _ in WIDER_GUARDS])
def test_the_wider_family_also_refuses_a_trailing_newline(relative_path, constant, good):
    compiled = re.compile(_pattern(relative_path, constant))

    assert compiled.match(good), f"{constant} rejects a value it must still accept: {good!r}"
    assert not compiled.match(good + "\n"), f"{constant} still accepts a trailing newline - use \\Z, not $"


def test_the_setup_wizard_host_is_the_one_that_reaches_a_config_file():
    """Named on its own because the consequence differs from the extractors beside it: this value
    is written to `REVERSE_PROXY_HOST` unmodified and rendered into nginx."""
    compiled = re.compile(_pattern("ui/app/routes/utils.py", "REVERSE_PROXY_PATH"))

    assert compiled.match("http://10.0.0.1")
    assert not compiled.match("http://10.0.0.1\n")
    assert not compiled.match("http://10.0.0.1\nproxy_set_header X-Evil evil;")


def test_every_guard_actually_moved_off_dollar():
    """Belt and braces: `\\Z` is the fix, and a future edit back to `$` reintroduces the hole.

    The behavioural test above would catch that too; this one names the cause in the failure
    message so nobody has to rediscover why `$` is wrong.
    """
    every = GUARDS + [(path, constant) for path, constant, _ in WIDER_GUARDS]
    offenders = [f"{path}:{constant}" for path, constant in every if _pattern(path, constant).endswith("$")]
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


def test_the_config_routes_do_not_re_inline_the_pattern_they_have_a_constant_for():
    r"""The declaration was anchored; two call sites 450 lines below still inlined `$`.

    `test_every_guard_actually_moved_off_dollar` above reads the *constant*, so it reported a
    clean bill of health while `configs_new` validated a raw `request.form["name"]` against
    `^[\w_-]{1,255}$`. A guard that only inspects the declaration cannot see a call site that
    ignores it -- and the declaration in that file even carries a comment explaining why `$` is
    wrong, four hundred lines above two uses of `$`.

    So this asserts the *shape* rather than the anchor: the pattern is written out exactly once,
    in the `CONFIG_NAME_RX` assignment. That catches a re-inlined `$` (the defect), a re-inlined
    `\Z` (the same drift, correct today), and the constant being deleted (count drops to zero).
    """
    source = (_SRC / "ui/app/routes/configs.py").read_text(encoding="utf-8")
    literals = re.findall(r'r"\^\[\\w_-\]\{1,255\}\\?[Z$]"', source)
    assert len(literals) == 1, f"the config-name pattern is spelled out {len(literals)}x; only the CONFIG_NAME_RX assignment should"
    # And the call sites really do route through it, so the count above cannot be satisfied by
    # deleting the validation entirely.
    assert source.count("match(CONFIG_NAME_RX,") >= 3, "the config routes stopped validating through CONFIG_NAME_RX"
