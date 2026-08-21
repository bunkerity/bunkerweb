"""The all-in-one supervisord units must survive their own parser.

supervisord reads `supervisor.d/*.ini` with `supervisor.options.UnhosedConfigParser`, a
`configparser.ConfigParser` subclass with `inline_comment_prefixes=(";",)`. That rule strips
everything from the first `;` that is **preceded by whitespace** to the end of the line -- inside a
quoted shell command exactly as readily as after a real setting.

`crowdsec.ini` matched a URL prefix with `case ... esac`, and a `case` item ends in `;;`. Written as
`... config.yaml ;; *) ...` the parser cut the 446-character `command=` down to 267, mid-`sh -c '`.
supervisord then failed to `shlex` the unterminated quote and put crowdsec in FATAL, so an
all-in-one with `USE_CROWDSEC=yes` ran no CrowdSec at all -- while every other unit, the container
health check and the logs looked normal. Nothing in the file is invalid shell; the syntax was never
the problem, the comment rule was.

The fix is `;;` with no space in front of it. That is two characters and nothing stops the next
edit from putting the space back, which is what this guard is for: it re-runs the measurement that
found the defect, over every unit, on every test run.

`interpolation=None` is not a detail. supervisord expands `%(...)s` in a later pass, so at parse
time `worker.ini`'s `--hostname=worker@%%h` stays `%%h`. With stdlib interpolation left on, the
stand-in collapses it to `%h`, and the resulting one-character shortfall reads as a truncation that
is not there. Measured against the real `UnhosedConfigParser` on 2026-08-20: with
`interpolation=None` the two agree on all nine units, with it on they disagree on `worker`.
"""

from configparser import ConfigParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UNITS_DIR = ROOT / "src" / "all-in-one" / "supervisor.d"

# The shape that broke, kept verbatim rather than read from git: this file has to be able to prove
# its own detector still bites even when the tree no longer contains the defect.
TRUNCATING_UNIT = (
    "[program:crowdsec]\n"
    'command=sh -c \'if [ "${USE_CROWDSEC}" = "yes" ]; then case "${CROWDSEC_API:-http://127.0.0.1:8000}" in '
    "http://127.0.0.1*|http://localhost*) exec /usr/local/bin/crowdsec -c /etc/crowdsec/config.yaml ;; "
    "*) echo disabled && exit 0 ;; esac; else echo disabled && exit 0; fi'\n"
)


def declared_command(text: str) -> str:
    """The `command=` value as a human reading the file sees it."""
    return next(line[len("command=") :] for line in text.splitlines() if line.startswith("command="))


def parsed_command(text: str, program: str) -> str:
    """The same value as supervisord receives it."""
    parser = ConfigParser(inline_comment_prefixes=(";",), strict=False, interpolation=None)
    parser.read_string(text)
    return parser.get(f"program:{program}", "command")


def truncated_units(units_dir: Path = UNITS_DIR) -> list:
    losses = []
    for unit in sorted(units_dir.glob("*.ini")):
        text = unit.read_text(encoding="utf-8")
        declared, parsed = declared_command(text), parsed_command(text, unit.stem)
        if declared != parsed:
            losses.append((unit.stem, len(declared), len(parsed)))
    return losses


def test_every_all_in_one_unit_parses_to_its_full_declared_command():
    """A failure names the unit and both lengths. The fix is in the `.ini`, never here: find the
    ` ;` in its `command=` value and remove the space, or move the logic into a script next to
    `service-log-wrapper.sh` so the value has no shell punctuation left to lose."""
    losses = truncated_units()
    assert losses == [], "supervisord will truncate: " + "; ".join(f"{unit} {declared} -> {parsed} chars" for unit, declared, parsed in losses)


def test_all_nine_units_are_actually_being_checked():
    """Anti-vacuity on the walker: a guard that finds no files passes forever."""
    assert len(list(UNITS_DIR.glob("*.ini"))) == 9, "the all-in-one unit count changed -- read the new unit, then update this number"


def test_the_detector_still_catches_the_shape_that_broke_crowdsec(tmp_path):
    """Anti-vacuity on the detector itself, using the pre-fix `command=` value."""
    unit = tmp_path / "crowdsec.ini"
    unit.write_text(TRUNCATING_UNIT, encoding="utf-8")
    assert [name for name, _, _ in truncated_units(tmp_path)] == ["crowdsec"]

    fixed = TRUNCATING_UNIT.replace(" ;;", ";;")
    unit.write_text(fixed, encoding="utf-8")
    assert truncated_units(tmp_path) == [], "removing the space did not stop the truncation -- the parser rule assumed here is wrong"


def test_the_stand_in_agrees_with_the_real_supervisor_parser():
    """Pins the assumption. Skipped where supervisor is not installed (it is not a test dep), which
    is why the checks above use stdlib rather than depending on this one."""
    options = pytest.importorskip("supervisor.options", reason="supervisor is not a test dependency")
    for unit in sorted(UNITS_DIR.glob("*.ini")):
        text = unit.read_text(encoding="utf-8")
        real = options.UnhosedConfigParser()
        real.read_string(text)
        assert real.get(f"program:{unit.stem}", "command") == parsed_command(text, unit.stem), f"{unit.stem}: stand-in and supervisor disagree"
