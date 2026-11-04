"""Rendering workers inherit globals even after another caller selects forkserver."""

import multiprocessing as mp
from pathlib import Path

import pytest

import Templator as T


@pytest.fixture(params=[None, "forkserver"])
def default_context(request):
    previous = mp.get_start_method(allow_none=True)
    mp.set_start_method(request.param, force=True)
    try:
        yield request.param
    finally:
        mp.set_start_method(previous, force=True)


def test_workers_inherit_globals_without_changing_the_default_context(tmp_path, monkeypatch, default_context):
    templates = tmp_path / "templates"
    (templates / "server-http").mkdir(parents=True)
    (templates / "server-http/probe.conf").write_text('{{ import("pathlib").Path(PROBE_PATH).is_file() }}\n')
    for name in ("core", "plugins", "pro-plugins"):
        (tmp_path / name).mkdir()
    probe = tmp_path / "absent-ca.pem"
    assert not probe.exists()
    real_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: path == probe or real_is_file(path))
    monkeypatch.setattr(T, "sep", str(tmp_path))
    config = {"SERVER_NAME": "app.example", "SSL_ECDH_CURVE": "prime256v1", "PROBE_PATH": str(probe)}
    output = tmp_path / "output"
    templator = T.Templator(
        str(templates),
        str(tmp_path / "core"),
        str(tmp_path / "plugins"),
        str(tmp_path / "pro-plugins"),
        str(output),
        "/etc/nginx",
        config,
        config.copy(),
        config.copy(),
    )

    assert templator.render() == []
    assert (output / "probe.conf").read_text() == "True\n"
    assert mp.get_start_method(allow_none=True) == default_context
