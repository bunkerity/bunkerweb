"""``tests/scripts/run.sh`` must give a spec's ``retries: N`` exactly N retries.

The loop used to decrement the counter *before* testing it, so `retries: N` bought N-1 actual
retries and `retries: 1` -- what the four `whitelist;rdns*` actions carry, among others -- bought
none: the first failure decremented 1 to 0 and took the `exit 1` branch. That made every one of
those actions single-shot while the spec said otherwise, and it hid nothing useful: a genuinely
broken spec still failed, a flaky one just failed sooner.

There is no way to run `run.sh` end to end here (it drives Docker, a state Redis and the whole
integration stack), so this executes **the shipped loop itself**: the region between the
``while``/``done`` pair is cut out of the real file and run under bash with every external call
stubbed. The extraction asserts it found exactly one such pair, so a reshaped loop fails loudly
instead of quietly testing nothing.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUN_SH = ROOT / "tests" / "scripts" / "run.sh"

# The slice starts at the redis read, NOT at the `while`: the attempt budget is computed between
# the two, and a harness that computed it itself would keep passing if that arithmetic regressed --
# which is precisely the bug being fixed here.
START_LINE = "    retries=$(redis_cli get retries)"
WHILE_LINE = '    while [ "$attempts" -gt 0 ] ; do'
DONE_LINE = "    done"


def _extract_loop() -> str:
    """Cut the retry budget and its loop out of run.sh, verbatim."""
    lines = RUN_SH.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line == START_LINE]
    assert len(starts) == 1, f"expected exactly one {START_LINE!r} in run.sh, found {len(starts)}"
    start = starts[0]
    whiles = [i for i in range(start, len(lines)) if lines[i] == WHILE_LINE]
    assert whiles, f"no {WHILE_LINE!r} after the retry budget in run.sh"
    ends = [i for i in range(whiles[0] + 1, len(lines)) if lines[i] == DONE_LINE]
    assert ends, f"no {DONE_LINE!r} closing the attempts loop"
    end = ends[0] + 1
    return "\n".join(lines[start:end])


# Everything the loop body reaches out to. `restart_stack` is pinned to 0 so the stack-restart
# block is skipped entirely -- it is not what this test is about, and it is what makes the rest
# of the body stubbable in a dozen lines.
HARNESS = """
set -u
restart_stack=0
full_clean=0
first_run=false
type=core
test=whitelist:rdns
integration=Docker
category=whitelist
release=dev
IS_FREEBSD=false

log() { :; }
log_stack() { :; }
# `redis_cli get retries` is how the script learns the budget, so the stub answers that one from
# the environment and everything else with the value that keeps the stack-restart block skipped.
redis_cli() {
    if [ "${1:-}" = "get" ] && [ "${2:-}" = "retries" ] ; then
        echo "$RETRIES"
    else
        echo 0
    fi
}

# Two different python3 calls reach this stub: the action itself, and the regeneration the
# loop runs before every retry (without it a full_clean retry starts a stack with no
# application -- see run.sh). Only the first is an attempt; the second must succeed, or the
# loop's error branch aborts the category.
python3() {
    case "${1:-}" in
        tests/generate.py)
            echo "generate" >> "$GENERATIONS_FILE"
            return 0
            ;;
    esac

    echo "attempt" >> "$ATTEMPTS_FILE"
    local seen
    seen=$(wc -l < "$ATTEMPTS_FILE")
    if [ "$seen" -eq "$PASS_ON" ] ; then
        return 0
    fi
    return 1
}

%s
"""


def _run(retries: int, pass_on: int, tmp_path: Path):
    """Run the extracted loop; PASS_ON=0 means the spec never passes."""
    attempts_file = tmp_path / f"attempts-{retries}-{pass_on}"
    attempts_file.write_text("")
    generations_file = tmp_path / f"generations-{retries}-{pass_on}"
    generations_file.write_text("")
    script = HARNESS % _extract_loop()
    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "RETRIES": str(retries),
            "PASS_ON": str(pass_on),
            "ATTEMPTS_FILE": attempts_file.as_posix(),
            "GENERATIONS_FILE": generations_file.as_posix(),
        },
    )
    attempts = len(attempts_file.read_text().splitlines())
    generations = len(generations_file.read_text().splitlines())
    return attempts, generations, proc.returncode, proc.stderr


@pytest.mark.parametrize(
    ("retries", "expected_attempts"),
    [
        (0, 1),  # no retries configured: one attempt, then give up
        (1, 2),  # THE regression: this used to make exactly one attempt
        (2, 3),
        (3, 4),
    ],
)
def test_a_failing_test_is_attempted_retries_plus_one_times(retries, expected_attempts, tmp_path):
    attempts, _, returncode, stderr = _run(retries, pass_on=0, tmp_path=tmp_path)
    assert attempts == expected_attempts, f"retries={retries} ran {attempts} attempt(s): {stderr}"
    assert returncode == 1, "a spec that never passes must still fail the job"


def test_the_loop_stops_at_the_first_pass(tmp_path):
    # retries: 2 but the second attempt succeeds -> three attempts must NOT be made.
    attempts, _, returncode, stderr = _run(2, pass_on=2, tmp_path=tmp_path)
    assert attempts == 2, f"the loop kept going after a pass: {stderr}"
    assert returncode == 0, "a passing retry must not fail the job"


@pytest.mark.parametrize(("retries", "expected_generations"), [(0, 0), (1, 1), (3, 3)])
def test_every_retry_regenerates_the_action(retries, expected_generations, tmp_path):
    """A retry must re-run generate.py -- once per retry, never before the first attempt.

    `generate.py` runs once per action, outside this loop, and writes /tmp/services.yml. A
    `full_clean` attempt ends in `cleanup_stack`, which deletes that file, and `start.sh` only
    deploys the application when it is there. Without a regeneration the retry therefore tests a
    stack with no application: `Autoconf;headers` spent all three of `check_cookie_flags_ssl`'s
    retries reporting an absent cookie, which is not what failed, and the real error was lost.
    """
    _, generations, _, stderr = _run(retries, pass_on=0, tmp_path=tmp_path)
    assert generations == expected_generations, f"retries={retries} regenerated {generations} time(s): {stderr}"
