"""Run the shipped TERM trap and wait logic with a child that shuts down slowly."""

import re

import pytest
from _t7_helpers import bash, block, function, retarget, source

HARNESS = """
log() {{ :; }}
{trap_function}
{trap_registration}
trap 'printf "parent exited (%s)\\n" "$?"' EXIT
(
    trap 'sleep 0.25; echo "child finished"; exit 42' TERM
    echo ready > "$1/ready"
    while :; do sleep 0.01; done
) &
pid=$!
echo "$pid" > "$1/var/run/bunkerweb/{component}.pid"
while [ ! -f "$1/ready" ]; do sleep 0.01; done
parent=$$
(sleep 0.05; kill -s TERM "$parent") &
{wait_and_exit}
"""


@pytest.mark.parametrize("component", ["scheduler", "ui", "api", "autoconf"])
def test_entrypoint_waits_for_graceful_shutdown_and_preserves_child_status(tmp_path, component):
    script = source(f"src/{component}/entrypoint.sh")
    (tmp_path / "var/run/bunkerweb").mkdir(parents=True)
    program = HARNESS.format(
        component=component,
        trap_function=function(script, "trap_exit"),
        trap_registration=block(script, r"^trap .* TERM INT QUIT$", "stop trap"),
        wait_and_exit=script.split('\npid="$!"\n', 1)[1],
    )
    result = bash(retarget(program, tmp_path, "/var/run", "/var/tmp"), str(tmp_path), timeout=5)
    assert result.stdout.splitlines() == ["child finished", "parent exited (42)"]
    assert result.returncode == 42, result.stderr


FAKE_CHILD = """
log() {{ :; }}
{trap_function}
{trap_registration}
trap 'printf "parent exited (%s)\\n" "$?"' EXIT
fake_child() {{
    local label="${{1:-child}}" delay="${{2:-0.25}}"
    trap "sleep $delay; echo '$label finished'; exit 42" TERM
    echo "$label started"
    while :; do sleep 0.01; done
}}
{before}
{launch_and_wait}
"""


LAUNCH_SECTION = {
    "scheduler": "# execute jobs",
    "autoconf": "# execute jobs",
    "api": "# Start the main Gunicorn process",
    "ui": "# Start a temporary Gunicorn process",
}


def _program(component, tmp_path, before):
    script = source(f"src/{component}/entrypoint.sh")
    (tmp_path / "var/run/bunkerweb").mkdir(parents=True)
    # From the comment that opens the launch section to the end, with every real launch swapped for fake_child.
    start = script.index(LAUNCH_SECTION[component])
    tail = script[start:]
    tail = re.sub(r"^.* &$", "fake_child &", tail, flags=re.M)
    program = FAKE_CHILD.format(
        trap_function=function(script, "trap_exit"),
        trap_registration=block(script, r"^trap .* TERM INT QUIT$", "stop trap"),
        before=before,
        launch_and_wait=tail,
    )
    return retarget(program, tmp_path, "/var/run", "/var/tmp")


@pytest.mark.parametrize("component", ["scheduler", "ui", "api", "autoconf"])
def test_stop_after_child_start_without_pid_file_reaches_the_child(tmp_path, component):
    # The child has started but wrote no PID file yet: the stop must still reach it, not be dropped.
    program = _program(component, tmp_path, '(sleep 0.3; kill -s TERM "$$") &')
    result = bash(program, str(tmp_path), timeout=5)
    assert "child finished" in result.stdout, result.stderr
    # The UI also starts a temporary child, which can print after the parent has exited.
    assert "parent exited (42)" in result.stdout.splitlines()
    assert result.returncode == 42, result.stderr


@pytest.mark.parametrize("component", ["scheduler", "ui", "api", "autoconf"])
def test_stop_before_child_start_never_starts_the_child(tmp_path, component):
    program = _program(component, tmp_path, 'kill -s TERM "$$"')
    result = bash(program, str(tmp_path), timeout=5)
    assert "child started" not in result.stdout
    assert result.stdout.splitlines()[-1] == "parent exited (143)"
    assert result.returncode == 143, result.stderr


def _ui_program(tmp_path, before, first_launch, after_first_launch=""):
    # The UI starts two children: the temporary one, then the main one. Only the first launch line is rewritten by `first_launch`.
    program = _program("ui", tmp_path, before)
    program = program.replace("fake_child &", first_launch, 1)
    # Parent-side marker: the main child can be signalled before it prints anything.
    program = program.replace("fake_child &", "echo main launched\nfake_child &", 1)
    return program.replace('tmp_pid="$!"', 'tmp_pid="$!"\n' + after_first_launch, 1)


def test_ui_stop_between_the_two_launches_never_starts_the_main_child(tmp_path):
    # TERM lands once the temporary child runs and before the main one is launched.
    # The sleep lets the temporary child install its own TERM trap first.
    program = _ui_program(tmp_path, "", "fake_child tmp 0.4 &", 'sleep 0.2; kill -s TERM "$$"')
    result = bash(program, str(tmp_path), timeout=5)
    lines = result.stdout.splitlines()
    assert "main launched" not in lines, lines
    # The entrypoint waits for the temporary child by its PID before it exits: no PID file exists here.
    assert lines[-2:] == ["tmp finished", "parent exited (143)"], lines
    assert result.returncode == 143, result.stderr


def test_ui_waits_for_the_temporary_child_without_a_pid_file(tmp_path):
    # The temporary child outlives the main one and wrote no PID file: the entrypoint must still wait for it.
    program = _ui_program(tmp_path, '(sleep 0.3; kill -s TERM "$$") &', "fake_child tmp 0.8 &")
    result = bash(program, str(tmp_path), timeout=10)
    lines = result.stdout.splitlines()
    assert lines[-2:] == ["tmp finished", "parent exited (42)"], lines
    assert result.returncode == 42, result.stderr


def test_ui_stop_does_not_wait_for_the_error_page_to_be_dismissed(tmp_path):
    # A startup error left ui.error behind and TERM arrives with no PID file: the temporary child outlives the main one, then both exit.
    (tmp_path / "var/tmp/bunkerweb").mkdir(parents=True)
    (tmp_path / "var/tmp/bunkerweb/ui.error").write_text("boom", encoding="utf-8")
    program = _ui_program(tmp_path, '(sleep 0.3; kill -s TERM "$$") &', "fake_child tmp 0.8 &")
    result = bash(program, str(tmp_path), timeout=10)
    lines = result.stdout.splitlines()
    assert lines[-2:] == ["tmp finished", "parent exited (42)"], lines
    assert result.returncode == 42, result.stderr
