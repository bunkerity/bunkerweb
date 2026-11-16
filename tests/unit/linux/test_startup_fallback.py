"""The shipped startup scripts keep a working config, fall back once, and never outlive a stop request.

The Docker entrypoint and the Linux start script run whole against a temporary root with stub ``nginx`` and
``python3`` (see ``_startup_sandbox``). ``nginx -t`` proves nothing about ``init_by_lua``: only a master
that actually starts does, so the stubs fail the start itself.
"""

import os
import signal

import pytest
from _startup_sandbox import Sandbox

VARIANTS = ["docker", "linux"]


def _keep(box, value):
    if box.variant == "linux":
        (box.root / "etc/bunkerweb/variables.env").write_text(f"KEEP_CONFIG_ON_RESTART={value}\n")
    box.control("keep", value)


def _launch(box):
    process = box.start()
    return process


def _running(box):
    return box.pid_file.exists()


def _end(box, process):
    """Stop the running instance the way its integration does, and return the script's exit status."""
    if box.variant == "docker":
        os.kill(process.pid, signal.SIGTERM)
    else:
        box.stop_nginx()
    return box.finish(process)


def _renders(box):
    return [call for call in box.calls if call.startswith("render ")]


def _starts(box):
    return [call.split("kind=")[1] for call in box.calls if call.startswith("nginx start")]


@pytest.fixture(params=VARIANTS)
def box(request, tmp_path):
    return Sandbox(tmp_path, request.param)


def test_kept_config_that_starts_is_not_replaced(box):
    box.keep_a_config()
    process = _launch(box)
    box.wait_for(lambda: _running(box))
    assert _renders(box) == []
    assert _starts(box) == ["kept"]
    assert _end(box, process) == 0


def test_kept_config_that_fails_to_start_falls_back_once(box):
    box.keep_a_config()
    box.control("nginx_mode", "kept-fails")
    process = _launch(box)
    box.wait_for(lambda: _running(box))
    assert _starts(box) == ["kept", "loading"]
    assert len(_renders(box)) == 1
    # The fallback renders before its start, and the failed kept start came first
    assert box.calls.index("nginx start kind=kept") < box.calls.index(_renders(box)[0]) < box.calls.index("nginx start kind=loading")
    assert not (box.root / "var/tmp/bunkerweb_needs_config").exists()
    assert _end(box, process) == 0


def test_fallback_render_failure_exits_nonzero_without_a_second_start(box):
    box.keep_a_config()
    box.control("nginx_mode", "kept-fails")
    box.control("render_rc", "3")
    process = _launch(box)
    assert box.finish(process) != 0
    assert _starts(box) == ["kept"]
    assert len(_renders(box)) == 1


def test_fallback_start_failure_exits_nonzero_after_exactly_one_fallback(box):
    box.keep_a_config()
    box.control("nginx_mode", "all-fail")
    process = _launch(box)
    assert box.finish(process) != 0
    assert _starts(box) == ["kept", "loading"]
    assert len(_renders(box)) == 1


def test_loading_render_failure_exits_nonzero_and_starts_nothing(box):
    box.keep_a_config()
    _keep(box, "no")
    box.control("render_rc", "3")
    process = _launch(box)
    assert box.finish(process) != 0
    assert _starts(box) == []


def test_loading_start_failure_exits_nonzero_without_another_render(box):
    box.keep_a_config()
    _keep(box, "no")
    box.control("nginx_mode", "all-fail")
    process = _launch(box)
    assert box.finish(process) != 0
    assert _starts(box) == ["loading"]
    assert len(_renders(box)) == 1


def test_interrupted_install_never_starts_the_kept_config(box):
    box.keep_a_config(interrupted=True)
    box.control("nginx_mode", "kept-fails")
    process = _launch(box)
    box.wait_for(lambda: _running(box))
    assert _starts(box) == ["loading"]
    assert _end(box, process) == 0


def test_stop_during_a_failing_kept_start_neither_falls_back_nor_starts_again(box):
    box.keep_a_config()
    box.control("nginx_mode", "slow-kept-fails")
    process = _launch(box)
    box.wait_for(lambda: _starts(box) == ["kept"])
    os.kill(process.pid, signal.SIGTERM)
    assert box.finish(process) == 0
    assert _renders(box) == []
    assert _starts(box) == ["kept"]


def test_stop_during_the_fallback_render_never_starts_nginx_again(box):
    box.keep_a_config()
    box.control("nginx_mode", "kept-fails")
    box.control("render_sleep", "1.5")
    process = _launch(box)
    box.wait_for(lambda: _renders(box) != [])
    os.kill(process.pid, signal.SIGTERM)
    assert box.finish(process) == 0
    assert _starts(box) == ["kept"]


def test_stop_during_the_first_render_never_starts_nginx(box):
    box.keep_a_config()
    _keep(box, "no")
    box.control("render_sleep", "1.5")
    process = _launch(box)
    box.wait_for(lambda: _renders(box) != [])
    os.kill(process.pid, signal.SIGTERM)
    assert box.finish(process) == 0
    assert _starts(box) == []
