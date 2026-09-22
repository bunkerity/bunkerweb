"""Run the shipped launcher with fake installed helpers and Celery masters."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("mode", ["defaults", "disabled", "heavy", "default", "stubborn", "warm"])
def test_entrypoint_lanes(tmp_path, mode):
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    (helpers / "utils.sh").write_text("log() { :; }; handle_docker_secrets() { :; }\n")
    (helpers / "data.sh").write_text("#!/bin/sh\nexit 0\n")
    (helpers / "data.sh").chmod(0o755)
    (tmp_path / "VERSION").write_text("test")
    (tmp_path / "worker").mkdir()
    (tmp_path / "worker/celery-loglevel.sh").symlink_to(ROOT / "src/worker/celery-loglevel.sh")
    # Only the database probe uses python3; the fake Celery has an absolute interpreter.
    (tmp_path / "python3").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "python3").chmod(0o755)
    celery = tmp_path / "celery"
    celery.write_text(
        f"#!{sys.executable}\n"
        "import json, os, signal, sys, time\nfrom pathlib import Path\n"
        "p = Path(os.environ['RECORD']) / (str(os.getpid()) + '.json')\n"
        "def stop(*_):\n"
        " p.with_suffix('.term').touch()\n"
        " if os.environ['MODE'] == 'stubborn': return\n"
        " if os.environ['MODE'] == 'warm': time.sleep(.4)\n"
        " sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "p.write_text(json.dumps(sys.argv[1:]))\n"
        "while True: time.sleep(.02)\n"
    )
    celery.chmod(0o755)
    script = tmp_path / "entrypoint.sh"
    script.write_text((ROOT / "src/worker/entrypoint.sh").read_text().replace("/usr/share/bunkerweb", str(tmp_path)))
    env = {k: v for k, v in os.environ.items() if not k.startswith("WORKER_")}
    env.update(PATH=f"{tmp_path}:{env['PATH']}", RECORD=str(tmp_path), MODE=mode, WORKER_FAILOVER_GRACE="0.1")
    if mode == "disabled":
        env.update(WORKER_HEAVY_QUEUES="", WORKER_QUEUES="default,heavy")
    proc = subprocess.Popen(["bash", str(script)], env=env, start_new_session=True)
    try:
        expected = 1 if mode == "disabled" else 2
        deadline = time.monotonic() + 5
        while len(list(tmp_path.glob("*.json"))) < expected and time.monotonic() < deadline:
            time.sleep(0.02)
        records = {int(p.stem): json.loads(p.read_text()) for p in tmp_path.glob("*.json")}
        queues = {args[args.index("-Q") + 1]: pid for pid, args in records.items()}
        assert set(queues) == ({"default,heavy"} if mode == "disabled" else {"default", "heavy"})
        if mode == "disabled":
            assert queues["default,heavy"] == proc.pid
        if mode in ("heavy", "default", "stubborn"):
            os.kill(queues["heavy" if mode == "stubborn" else mode], signal.SIGKILL if mode == "stubborn" else signal.SIGTERM)
        else:
            proc.terminate()
        status = proc.wait(timeout=3)
        assert status > 0 if mode in ("heavy", "default", "stubborn") else status == 0
        assert len(list(tmp_path.glob("*.term"))) == (1 if mode == "stubborn" else expected)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
