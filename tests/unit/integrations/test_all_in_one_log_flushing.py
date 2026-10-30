"""The All-in-one image must hand each log line to `docker logs` as it is produced.

`logstream.sh` (NGINX access/error + ModSecurity audit) and `service-log-wrapper.sh`
(every supervised Python service) pipe their output through `tr -d` to strip C0
control characters before tagging it. `tr` writes into a pipe, so libc gives it a
4 KiB *block* buffer: on a low-traffic stream the lines sit in that buffer instead of
reaching the container's stdout/stderr. The NGINX error log is exactly such a stream —
the ModSecurity/CRS detail line for a single blocked request never surfaces — and the
integration harness reads `docker logs`, so its `log:` assertions look for something
that has not been flushed yet.

These tests run the *shipped* pipelines against a temporary file and assert a single
line becomes visible promptly.
"""

from os import killpg, getpgid
from pathlib import Path
from shutil import which
from signal import SIGKILL
from subprocess import DEVNULL, Popen
from time import monotonic, sleep

import pytest

ROOT = Path(__file__).resolve().parents[3]
AIO_DIR = ROOT / "src" / "all-in-one"
LOGSTREAM = AIO_DIR / "logstream.sh"
WRAPPER = AIO_DIR / "service-log-wrapper.sh"

# Generous: we only need to tell "flushed per line" from "held until 4 KiB".
FLUSH_TIMEOUT = 10.0

pytestmark = pytest.mark.skipif(
    which("bash") is None or which("tail") is None or which("stdbuf") is None,
    reason="GNU shell tooling required (the fixed pipelines use stdbuf and sed -u)",
)


def shipped_tail_pipelines():
    """The `tail -F` pipelines logstream.sh actually ships, one per followed file."""
    return [line.strip() for line in LOGSTREAM.read_text(encoding="utf-8").splitlines() if "tail -F" in line and not line.lstrip().startswith("#")]


def runnable(pipeline: str, log_file: Path) -> str:
    """Re-point a shipped pipeline at a temp file, keeping every buffering-relevant stage."""
    command = pipeline.removeprefix("exec ").strip()
    command = command.replace('"$log_file"', f'"{log_file}"').replace("${prefix}", "[TAG] ")
    # The stderr variant would otherwise bypass the file we sample.
    return command.removesuffix(">&2").strip()


def wait_for(path: Path, needle: str) -> float:
    """Seconds until `needle` shows up in `path`, or FLUSH_TIMEOUT if it never does."""
    started = monotonic()
    while monotonic() - started < FLUSH_TIMEOUT:
        if needle in path.read_text(encoding="utf-8", errors="replace"):
            return monotonic() - started
        sleep(0.1)
    return FLUSH_TIMEOUT


def run_detached(argv, out_file: Path):
    # Popen dups the fd, so closing our handle right away leaks nothing to the child.
    with out_file.open("w", encoding="utf-8") as handle:
        return Popen(argv, stdout=handle, stderr=DEVNULL, start_new_session=True)


def stop(process):
    try:
        killpg(getpgid(process.pid), SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()
    process.wait(timeout=10)


@pytest.mark.parametrize("pipeline", shipped_tail_pipelines(), ids=lambda p: p.split('"')[1] if '"' in p else p[:40])
def test_logstream_pipelines_flush_a_single_line(tmp_path, pipeline):
    log_file = tmp_path / "followed.log"
    log_file.touch()
    out_file = tmp_path / "streamed.txt"

    process = run_detached(["bash", "-c", runnable(pipeline, log_file)], out_file)
    try:
        sleep(1)  # let tail attach before the only line we write
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write('ModSecurity: Access denied with code 403 [ver "OWASP_CRS/4.19.0"]\n')

        elapsed = wait_for(out_file, '[TAG] ModSecurity: Access denied with code 403 [ver "OWASP_CRS/4.19.0"]')
        assert elapsed < FLUSH_TIMEOUT, f"single line never reached the stream in {FLUSH_TIMEOUT}s: {pipeline}"
    finally:
        stop(process)


def test_service_log_wrapper_flushes_a_single_line(tmp_path):
    out_file = tmp_path / "streamed.txt"

    process = run_detached(
        [str(WRAPPER), "unit-test", "[TEST] ", "bash", "-c", "printf 'service line\\n'; sleep 60"],
        out_file,
    )
    try:
        elapsed = wait_for(out_file, "[TEST] service line")
        assert elapsed < FLUSH_TIMEOUT, f"single line never reached the stream in {FLUSH_TIMEOUT}s"
    finally:
        stop(process)


def test_logstream_ships_one_pipeline_per_stream_branch():
    # Guards the parametrisation above against silently collapsing to zero cases. Two, not
    # three: logstream.sh follows three FILES through one function with two stream BRANCHES
    # (stdout and stderr) — a fourth followed file would not move this count.
    assert len(shipped_tail_pipelines()) == 2
