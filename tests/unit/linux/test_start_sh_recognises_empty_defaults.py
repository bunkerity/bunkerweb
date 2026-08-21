r"""`variables.env` keys must be recognised by existence, not by a non-empty default.

`start.sh` builds `/var/tmp/bunkerweb/tmp.env` by filtering `variables.env` against a `defaults`
associative array. The filter was `[[ -n "${defaults[$key]}" ]]`, which tests the default's
*value*. `[API_TOKEN]=""` is the only key in that array declared empty, so it was the only key the
filter rejected -- an operator could set `API_TOKEN` in `variables.env`, see it accepted with no
warning, and get a temp config with no token at all. Every other setting worked, which is why it
read as an API problem rather than a parsing one.

The loop is lifted out of the shipped script rather than retyped, so a rewrite there breaks this
test instead of leaving it asserting a copy that no longer runs.
"""

import re
import subprocess
from pathlib import Path

import pytest

START_SH = Path(__file__).resolve().parents[3] / "src" / "linux" / "scripts" / "start.sh"


def _region(pattern: str, name: str) -> str:
    match = re.search(pattern, START_SH.read_text(encoding="utf-8"), re.S)
    assert match, f"{name} no longer matches in start.sh -- re-read the script before trusting this test"
    return match.group(0)


DEFAULTS = _region(r"declare -A defaults=\(.*?\n\s*\)\n", "the defaults array")
PARSE_LOOP = _region(r"\s*while IFS='=' read -r key value; do.*?done < \"\$env_file\"\n", "the variables.env parse loop")

HARNESS = """
{defaults}
env_file="{env_file}"
{loop}
echo "API_TOKEN=[${{API_TOKEN:-<unset>}}]"
echo "HTTP_PORT=[${{HTTP_PORT:-<unset>}}]"
"""


def _run(tmp_path, loop=PARSE_LOOP):
    env_file = tmp_path / "variables.env"
    env_file.write_text("# a comment\nAPI_TOKEN=s3cr3t\nHTTP_PORT=8080\nNOT_A_SETTING=nope\n", encoding="utf-8")
    script = HARNESS.format(defaults=DEFAULTS, env_file=env_file, loop=loop)
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_api_token_is_read_from_variables_env(tmp_path):
    assert "API_TOKEN=[s3cr3t]" in _run(tmp_path), "the token set in variables.env did not reach the config"


def test_an_ordinary_setting_still_works(tmp_path):
    """Anti-vacuity: the harness must be able to fail. If nothing were parsed at all, the test
    above would be the only red and could be mistaken for an API_TOKEN-specific quirk."""
    assert "HTTP_PORT=[8080]" in _run(tmp_path)


def test_the_old_predicate_is_what_dropped_the_token(tmp_path):
    """The defect, reproduced against the same harness -- so this file proves its own detector
    bites rather than asserting the fix's shape."""
    old = PARSE_LOOP.replace('[[ -v "defaults[$key]" ]]', '[[ -n "${defaults[$key]}" ]]')
    assert old != PARSE_LOOP, "the predicate moved; re-read the loop"
    out = _run(tmp_path, loop=old)

    assert "API_TOKEN=[<unset>]" in out, "the old predicate should have dropped the token"
    assert "HTTP_PORT=[8080]" in out, "the old predicate only ever dropped empty-defaulted keys"


def test_api_token_is_still_the_empty_defaulted_key_this_guards(tmp_path):
    """If API_TOKEN ever gains a non-empty default, the original bug stops being reachable through
    it -- but any *new* empty-defaulted key inherits the hazard, so name them all."""
    empty = re.findall(r"\[(\w+)\]=\"\"", DEFAULTS)

    assert "API_TOKEN" in empty, f"API_TOKEN is no longer declared empty; empty-defaulted keys are now {empty}"


@pytest.mark.parametrize("line", ["", "# comment", "   "])
def test_blank_and_comment_lines_are_still_skipped(tmp_path, line):
    env_file = tmp_path / "variables.env"
    env_file.write_text(f"{line}\nAPI_TOKEN=tok\n", encoding="utf-8")
    script = HARNESS.format(defaults=DEFAULTS, env_file=env_file, loop=PARSE_LOOP)
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert "API_TOKEN=[tok]" in result.stdout
