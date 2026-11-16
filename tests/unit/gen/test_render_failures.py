"""Incomplete configurations must fail generation instead of being shipped."""

import json
import logging
import os
import subprocess
import sys
from textwrap import dedent
from pathlib import Path

import pytest

import Templator as T

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def templator(tmp_path, monkeypatch):
    for name in ("templates", "core", "plugins", "pro-plugins"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(T, "sep", str(tmp_path))
    config = {"SERVER_NAME": "app.example", "SSL_ECDH_CURVE": "prime256v1"}
    return T.Templator(
        str(tmp_path / "templates"),
        str(tmp_path / "core"),
        str(tmp_path / "plugins"),
        str(tmp_path / "pro-plugins"),
        str(tmp_path / "output"),
        "/etc/nginx",
        config,
        config.copy(),
        config.copy(),
    )


@pytest.mark.parametrize("context", ["global", "server-http"])
def test_render_failure_is_fatal(tmp_path, monkeypatch, context):
    template = tmp_path / "templates" / context / "broken.conf"
    template.parent.mkdir(parents=True)
    template.write_text("{{ 1 / 0 }}\n")
    for name in ("core", "plugins", "pro-plugins"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(T, "sep", str(tmp_path))
    config = {"SERVER_NAME": "app.example", "SSL_ECDH_CURVE": "prime256v1"}
    instance = T.Templator(
        str(tmp_path / "templates"),
        str(tmp_path / "core"),
        str(tmp_path / "plugins"),
        str(tmp_path / "pro-plugins"),
        str(tmp_path / "output"),
        "/etc/nginx",
        config,
        config.copy(),
        config.copy(),
    )
    with pytest.raises(ZeroDivisionError):
        instance.render()


def test_variables_write_failure_is_fatal(templator, monkeypatch):
    original = Path.write_text

    def write(path, *args, **kwargs):
        if path.name == ".variables.env.tmp":
            raise OSError("disk full")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(OSError, match="disk full"):
        templator.render()


def test_failed_generator_stops_the_push_with_failure_exit_code(tmp_path):
    for name in ("templates/global", "core", "plugins", "pro-plugins", "output", "target"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "templates/global/broken.conf").write_text("{{ 1 / 0 }}\n")
    plugin = tmp_path / "core/probe/plugin.json"
    plugin.parent.mkdir()
    setting = {"context": "global", "default": "no", "help": "Probe", "id": "probe", "label": "Probe", "regex": "^(yes|no)$", "type": "check"}
    plugin.write_text(json.dumps({"id": "probe", "name": "Probe", "description": "Probe", "version": "1.0", "stream": "no", "settings": {"PROBE": setting}}))
    variables = tmp_path / "variables.env"
    variables.write_text("SERVER_NAME=app.example\nSSL_ECDH_CURVE=prime256v1\n")
    code = "import runpy, Templator, sys; Templator.sep = sys.argv.pop(1); runpy.run_path(sys.argv.pop(1), run_name='__main__')"
    args = [sys.executable, "-c", code, str(tmp_path), str(ROOT / "src/common/gen/main.py"), "--settings", str(ROOT / "src/common/settings.json")]
    for name in ("templates", "core", "plugins", "pro-plugins", "output", "target"):
        args.extend([f"--{name}", str(tmp_path / name)])
    args.extend(["--variables", str(variables)])
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    result = subprocess.run(args, capture_output=True, text=True, env=env)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "division by zero" in result.stdout + result.stderr, result.stdout + result.stderr
    assert "Generator successfully executed" not in result.stdout + result.stderr

    # Run the shipped publication gate with the real generator outcome.
    job = (ROOT / "src/common/core/jobs/jobs/push-configs.py").read_text()
    start = job.index("    if not _render_nginx_configs(rendered_path):")
    stop = job.index("    _record_failover(db, reload_responses", start)
    delivered = []
    namespace = {
        "_render_nginx_configs": lambda output: result.returncode == 0,
        "rendered_path": tmp_path / "candidate",
        "LOGGER": logging.getLogger("render-failure"),
        "sys_exit": sys.exit,
        "instances": [],
        "_build_api_caller": lambda instances: object(),
        "_push_all": lambda *args: delivered.append("push"),
        "_trigger_reload": lambda *args: delivered.append("reload"),
    }
    with pytest.raises(SystemExit) as exc:
        exec(compile(dedent(job[start:stop]), "<push-configs>", "exec"), namespace)
    assert exc.value.code == 2, "exit 1 means changed, not failed, in the job protocol"
    assert delivered == []
