"""The two CrowdSec reds of run 34054359264, as invariants instead of comments.

Both are state that survives a boundary it was supposed to die at, and both make an assertion
pass -- or fail -- for a reason that has nothing to do with the product:

* `cleanup_stack` cleared the CrowdSec helper compose only in its Docker/Autoconf branch. A
  mid-run `full_clean` therefore reset CrowdSec on Docker and not on Linux, where the `cs-data`
  volume kept the ban the stream arm had just earned for the test IP. A ban wins over a
  challenge, so `crowdsec;challenged_by_appsec` read "challenge status: 403" on the Linux arm of
  every attempt while Docker stayed green.
* `restart_stack: false` means the stack is not restarted before the NEXT action, so that action's
  `config:` is written to variables.env and never reaches the instance. The deferral arm declared
  `CROWDSEC_DEFER_TO_WORKFLOWS` on the action that asserts it, two `restart_stack: false` actions
  after the last restart: the setting never applied, `defer_verdict()` returned false on its first
  line, and `crowdsec;the_workflow_answers_instead_of_crowdsec` asserted 302 against a feature the
  run had switched off.

`restart_stack()` still carries the same branch confinement this module now guards against in
`cleanup_stack()`: it recreates CrowdSec on Docker/Autoconf only (utils.sh:1729-1743). That is
benign today because every `crowdsec_config` change in the spec sits at a `full_clean` boundary,
where `start.sh:741` does the recreation for every integration -- but the name of the test below
should not be read as "the whole CrowdSec lifecycle is integration-uniform". It is not.
"""

import re
from pathlib import Path

from yaml import safe_load

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "tests" / "scripts" / "utils.sh"
SPEC = ROOT / "tests" / "core" / "crowdsec.yml"
COMPOSE = ROOT / "tests" / "misc" / "docker" / "crowdsec.yml"


def _cleanup_stack_body():
    text = UTILS.read_text(encoding="utf-8")
    start = text.index("function cleanup_stack () {")
    end = text.index("\nfunction ", start + 1)
    return text[start:end]


BODY = _cleanup_stack_body()

# Function-level indentation. Every branch of the integration chain indents its body by eight, so
# four is the one thing that proves the block is not confined to a single integration -- which is
# exactly what the Linux arm needed and did not have. Only the indentation and the `crowdsec` token
# are pinned: the matcher flags, the quoting and the spacing carry no part of the invariant, and a
# test that reds when `grep -q` becomes `grep -qx` reports a defect that is not there.
FUNCTION_LEVEL_CROWDSEC = re.compile(
    r"^    if .*\bcrowdsec\b.* ; then$\n(?P<block>(?:^(?: {8,}.*)?\n)*?)^    fi$",
    re.MULTILINE,
)


def test_the_cleanup_parser_still_sees_the_integration_chain():
    """Without this the two assertions below would pass on a file that no longer has branches."""
    assert 'elif [ "$integration" == "Linux" ] && ! $IS_FREEBSD ; then' in BODY
    assert 'elif [ "$integration" == "All-in-one" ] ; then' in BODY


def test_full_clean_clears_crowdsec_for_every_integration():
    match = FUNCTION_LEVEL_CROWDSEC.search(BODY)
    assert match, "cleanup_stack no longer tears CrowdSec down outside the integration chain"

    block = match.group("block")
    assert "docker compose -f tests/misc/docker/crowdsec.yml down -v" in block, "a `down` without `-v` keeps cs-data, and with it the decisions"
    # start.sh:741 only brings the container back when this key is set, so dropping it would swap
    # a stale CrowdSec for no CrowdSec at all.
    assert "redis_cli set restart_crowdsec 1" in block

    # The guard matches the WHOLE line (`grep -qx`), so the teardown only fires while the container
    # is named exactly this. Nothing else ties the two files together: rename it there, or drop
    # `container_name` and let compose prefix it, and cleanup_stack skips the teardown SILENTLY --
    # cs-data survives the full_clean and `challenged_by_appsec` reds with "challenge status: 403"
    # again, with no failing command anywhere to point at it.
    assert "grep -qx" in match.group(0), "a substring match would fire on a foreign container and fail the compose call"
    assert "container_name: crowdsec\n" in COMPOSE.read_text(encoding="utf-8")


def test_no_action_declares_a_config_the_previous_action_prevents_from_applying():
    """`restart_stack: false` on action N means action N+1's `config:` is written and never used.

    `config:` only. `crowdsec_config:` has a different and stricter precondition -- it is applied
    through `restart_crowdsec`, which only `start.sh:741` consumes, and start.sh only runs on
    `first_run` or `full_clean` -- so the same walk would report offenders that are correct. Every
    `crowdsec_config` in this spec sits at a `full_clean` boundary today; checking that properly
    means modelling the restart_crowdsec/start.sh pair, which this test deliberately does not.
    The walk is also document order, not per-integration order: sound here because the one arm that
    filters on `integrations:` is contiguous and Docker-only.
    """
    actions = safe_load(SPEC.read_text(encoding="utf-8"))["actions"]
    names = list(actions)
    assert len(names) > 10, f"the spec no longer looks like the one this test walks: {names}"

    offenders = []
    for previous, current in zip(names, names[1:]):
        if actions[previous].get("restart_stack", True):
            continue
        # No `config:` at all is the deliberate form: the action inherits the running instance,
        # which is what blocked_stream and banned_after_challenge rely on.
        if "config" not in actions[current]:
            continue
        if actions[current]["config"] != actions[previous].get("config"):
            offenders.append(f"{current} declares a config the unrestarted {previous} cannot apply")

    assert not offenders, offenders
