"""LX1-04/07: log payload modes and bounded reloads of the existing Gunicorn master."""

import re
import stat

import pytest
from _t7_helpers import ROOT, bash, function, retarget, source


@pytest.mark.parametrize("service", ["api", "ui"])
@pytest.mark.parametrize("pid,signal_rc", [("12345", 0), (None, 0), ("", 0), ("-1", 0), ("0", 0), ("oops", 0), ("12 34", 0), ("12345", 1)])
def test_reload_signals_only_the_existing_master(tmp_path, service, pid, signal_rc):
    pidfile = tmp_path / "var/run/bunkerweb" / f"{service}.pid"
    pidfile.parent.mkdir(parents=True)
    if pid is not None:
        pidfile.write_text(pid)
    temporary = pidfile.with_name("tmp-ui.pid")
    temporary.write_text("67890")
    calls = tmp_path / "calls"
    reload = retarget(function(source(f"src/linux/scripts/bunkerweb-{service}.sh"), "reload"), tmp_path, "/var/run")
    result = bash(f"""
        API_PID_FILE='{pidfile}'
        stop() {{ echo stop >> '{calls}'; }}
        start() {{ echo start >> '{calls}'; }}
        sleep() {{ echo sleep >> '{calls}'; }}
        kill() {{ echo "$*" >> '{calls}'; return {signal_rc}; }}
        {reload}
        reload
    """)
    valid = pid == "12345"
    assert result.returncode == (0 if valid and signal_rc == 0 else 1), result.stdout + result.stderr
    actual = calls.read_text().splitlines() if calls.exists() else []
    assert actual == (["-s HUP 12345"] if valid else [])
    assert pidfile.exists() is (pid is not None)
    if pid is not None:
        assert pidfile.read_text() == pid
    assert temporary.read_text() == "67890"


RECIPES = sorted((ROOT / "src/linux").glob("Dockerfile-*"))


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda p: p.name)
@pytest.mark.parametrize("umask", ["022", "077"])
def test_recipe_creates_private_logs_in_the_same_run(tmp_path, recipe, umask):
    # Join Docker continuations, then keep RUN boundaries: umask in another RUN cannot help.
    text = re.sub(r"\\\n", "", recipe.read_text())
    runs = re.findall(r"^RUN (.*)$", text, re.M)
    creators = [run for run in runs if "touch /var/log/bunkerweb/error.log" in run]
    assert len(RECIPES) == 10 and len(creators) == 1
    start = creators[0].index("touch /var/log/bunkerweb/error.log")
    command = creators[0][start:]
    logdir = tmp_path / "var/log/bunkerweb"
    logdir.mkdir(parents=True)
    result = bash(f"umask {umask}\n{retarget(command, tmp_path, '/var/log')}")
    assert result.returncode == 0, result.stderr
    for name in ("error", "access", "modsec_audit"):
        assert stat.S_IMODE((logdir / f"{name}.log").stat().st_mode) == 0o640
