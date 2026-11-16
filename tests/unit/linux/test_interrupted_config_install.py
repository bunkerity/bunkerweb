"""Startup decisions run from the shipped shell, with paths confined to tmp_path."""

from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("relative", ["src/bw/entrypoint.sh", "src/linux/scripts/start.sh"])
@pytest.mark.parametrize("interrupted", [False, True])
def test_restart_does_not_keep_an_interrupted_install(tmp_path, relative, interrupted):
    text = (ROOT / relative).read_text()
    begin = text.index('tmp_env_path="', text.index("function start()") if "/linux/" in relative else 0)
    end = text.index('write_tmp_env_file "$tmp_env_path"', begin) if "/linux/" in relative else text.index('printf "%s\\n" "$tmp_env_content"', begin)
    block = text[begin:end]
    block = (
        block.replace("/etc/nginx", str(tmp_path / "nginx"))
        .replace("/var/tmp/bunkerweb", str(tmp_path / "runtime"))
        .replace('"/tmp/variables.env"', f'"{tmp_path}/variables.env"')
    )
    (tmp_path / "nginx").mkdir()
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime/tmp.env").touch()
    (tmp_path / "variables.env").touch()
    if interrupted:
        (tmp_path / "nginx/.bw-install-incomplete").touch()
    result = subprocess.run(
        [
            "bash",
            "-c",
            'log() { :; }; generate_tmp_env_content() { :; }; run_as_nginx() { "$@"; }; KEEP_CONFIG_ON_RESTART=yes;\n'
            + block
            + '\nprintf "regenerate=%s\\n" "$regenerate_temp_config"',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"regenerate={str(interrupted).lower()}"


@pytest.mark.parametrize("relative", ["src/bw/entrypoint.sh", "src/linux/scripts/start.sh"])
def test_generation_failure_prevents_nginx_start(relative):
    text = (ROOT / relative).read_text()
    indent = "    " if "/linux/" in relative else ""
    begin = text.index(indent + 'if [[ "$regenerate_temp_config" == "true" ]] ; then')
    end = text.index("\n" + indent + "fi", begin) + len(indent) + 3
    block = text[begin:end]
    # The block calls the shared render function: without its definition the call fails for the wrong reason
    function = text[text.index("function render_temp_config()") : text.index("\n}\n", text.index("function render_temp_config()")) + 3]
    assert "render_temp_config ||" in block
    result = subprocess.run(
        [
            "bash",
            "-c",
            "log() { :; }; python3() { return 7; }; run_as_nginx() { return 7; }; regenerate_temp_config=true; tmp_env_path=/unused; PYTHON_BIN=python3;\n"
            + function
            + "\n"
            + block
            + '\nprintf "started\\n"',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "started" not in result.stdout
