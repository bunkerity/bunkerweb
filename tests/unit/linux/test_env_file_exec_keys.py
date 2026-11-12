"""The service wrappers run as root and must not let an env file change how root runs programs.

`/etc/bunkerweb/variables.env` and the per-service `*.env` files are group-writable by the nginx user and
are read by `export_env_file` inside the root wrappers. A key such as `PATH`, `PYTHON_BIN`, `PYTHONPATH`,
`LD_PRELOAD` or `HOME` there would change the interpreter, the modules or the libraries root loads. The
helper now skips those keys (and warns, naming the key only); the root Python calls also ignore the user
site directory, and the scheduler wrapper no longer stages scripts under a fixed `/tmp` name.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from _t7_helpers import ROOT, bash, function, source

UTILS = ROOT / "src/common/helpers/utils.sh"
WRAPPERS = {name: source(f"src/linux/scripts/bunkerweb-{name}.sh") for name in ("scheduler", "ui", "api")}
SECRET = "attacker-value-1234"

DENIED_KEYS = (
    "PATH",
    "HOME",
    "SHELL",
    "ENV",
    "BASH_ENV",
    "IFS",
    "PS4",
    "PYTHON_BIN",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONNOUSERSITE",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "LD_AUDIT",
    "GCONV_PATH",
    "TMPDIR",
    "OPENSSL_CONF",
)


def _export(tmp_path: Path, contents: str, probe: str) -> subprocess.CompletedProcess:
    env_file = tmp_path / "variables.env"
    env_file.write_text(contents, encoding="utf-8")
    return bash(f'source "{UTILS}"; export_env_file "{env_file}"; {probe}', env={"PATH": os.environ["PATH"], "HOME": "/home/original"})


@pytest.mark.parametrize("key", DENIED_KEYS)
def test_a_key_that_changes_program_execution_is_not_exported(tmp_path, key):
    result = _export(tmp_path, f"{key}={SECRET}\nSAFE_SETTING=ok\n", f'echo "SAFE=$SAFE_SETTING"; echo "VALUE=${{{key}-unset}}"')

    assert "SAFE=ok" in result.stdout, f"a normal setting stopped being exported: {result.stdout!r} {result.stderr!r}"
    assert f"VALUE={SECRET}" not in result.stdout, f"{key} from the env file reached the root environment"
    assert SECRET not in result.stderr, "the warning must name the key, never the value"
    assert key in result.stderr, f"no warning for the skipped key {key}: {result.stderr!r}"


def test_only_the_normal_setting_is_exported(tmp_path):
    contents = "PATH=/tmp/evil\nLD_PRELOAD=/tmp/evil.so\nPYTHON_BIN=/tmp/evil-python\nUSE_REVERSE_PROXY=yes\nREVERSE_PROXY_URL_1=/api\n"
    result = _export(tmp_path, contents, 'env | grep -E "^(PATH|LD_PRELOAD|PYTHON_BIN|USE_REVERSE_PROXY|REVERSE_PROXY_URL_1)=" | sort')

    exported = dict(line.split("=", 1) for line in result.stdout.splitlines())
    assert exported.get("USE_REVERSE_PROXY") == "yes" and exported.get("REVERSE_PROXY_URL_1") == "/api", result.stdout
    assert "LD_PRELOAD" not in exported and "PYTHON_BIN" not in exported, result.stdout
    assert exported.get("PATH") != "/tmp/evil", result.stdout


@pytest.mark.parametrize("key", ["LD_ANYTHING", "PYTHONWHATEVER", "BASH_FUNC_x", "GLIBC_TUNABLES", "MALLOC_CHECK_"])
def test_whole_families_are_skipped(tmp_path, key):
    result = _export(tmp_path, f"{key}={SECRET}\n", f'echo "VALUE=${{{key}-unset}}"')

    assert "VALUE=unset" in result.stdout, f"{key} reached the environment: {result.stdout!r}"


def test_settings_that_resemble_a_denied_name_still_work(tmp_path):
    names = ("LOCAL_PHP_PATH", "REMOTE_PHP_PATH", "SSL_PROTOCOLS", "PROXY_CACHE_PATH_ZONE_SIZE", "LOG_LEVEL", "HOME_PAGE_URL", "ENVIRONMENT", "PATHS")
    result = _export(tmp_path, "".join(f"{name}=v-{name}\n" for name in names), "; ".join(f'echo "{n}=${n}"' for n in names))

    for name in names:
        assert f"{name}=v-{name}" in result.stdout, f"{name} is a real setting name and must not be skipped: {result.stdout!r}"
    assert not result.stderr.strip(), result.stderr


def test_every_shipped_setting_name_is_still_exported(tmp_path):
    import json

    names = set()
    for path in [ROOT / "src/common/settings.json", *sorted(ROOT.glob("src/common/core/*/plugin.json"))]:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = data.get("settings", data)
        names.update(key for key, value in settings.items() if isinstance(value, dict) and "id" in value)

    result = _export(tmp_path, "".join(f"{name}=x\n" for name in sorted(names)), "env | cut -d= -f1 | sort")

    exported = set(result.stdout.split())
    assert names <= exported, f"settings skipped by the guard: {sorted(names - exported)}"
    assert not result.stderr.strip(), result.stderr


# ---------------------------------------------------------------------------------------------
# the root Python calls ignore the user site directory
# ---------------------------------------------------------------------------------------------

SYSTEM_PYTHON = "/usr/bin/python3"


def _root_python_lines(text: str):
    """Lines that run `$PYTHON_BIN` directly (root), not through `run_as_nginx`."""
    for line in text.splitlines():
        stripped = line.strip()
        if "$PYTHON_BIN" in stripped and "run_as_nginx" not in stripped and not stripped.startswith(("#", "export", "if ! run_as_nginx")):
            yield stripped


def test_root_python_calls_skip_the_user_site():
    lines = [line for line in _root_python_lines(WRAPPERS["scheduler"])]
    assert lines, "the scheduler wrapper no longer runs python as root -- re-read it before trusting this test"
    for line in lines:
        assert re.search(r'\$PYTHON_BIN"? (-\w+ )*-s\b|\$PYTHON_BIN"? -[A-Za-z]*s[A-Za-z]* ', line), f"root python call does not pass -s: {line}"


@pytest.mark.skipif(not Path(SYSTEM_PYTHON).exists(), reason="needs a system python without a venv")
def test_a_home_from_the_env_file_cannot_plant_code_in_the_root_python(tmp_path):
    version = subprocess.run(
        [SYSTEM_PYTHON, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True, check=True
    ).stdout.strip()
    home = tmp_path / "fake-home"
    site_dir = home / ".local" / "lib" / f"python{version}" / "site-packages"
    site_dir.mkdir(parents=True)
    marker = tmp_path / "usercustomize-ran"
    (site_dir / "usercustomize.py").write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")

    # The exact interpreter prefix the scheduler wrapper uses for its root alembic call
    match = re.search(r'("?\$PYTHON_BIN[^\n]*?) -m alembic stamp', WRAPPERS["scheduler"])
    assert match, "the alembic stamp call no longer matches"
    prefix = match.group(1)

    env_file = tmp_path / "variables.env"
    env_file.write_text(f"HOME={home}\nPYTHONNOUSERSITE=\n", encoding="utf-8")
    script = f'source "{UTILS}"; export_env_file "{env_file}"; PYTHON_BIN={SYSTEM_PYTHON}; {prefix} -c "print(1)"'
    run_env = {"PATH": "/usr/bin:/bin", "HOME": "/root-home"}

    # Control: the fixture must really be able to plant code, or the assertion below proves nothing
    control = subprocess.run([SYSTEM_PYTHON, "-c", "print(1)"], env={"PATH": "/usr/bin:/bin", "HOME": str(home)}, capture_output=True, text=True, check=False)
    assert control.returncode == 0 and marker.exists(), f"fixture cannot plant a usercustomize module: {control.stderr}"
    marker.unlink()

    result = bash(script, env=run_env)

    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "the root python imported usercustomize from a HOME set by the env file"


# ---------------------------------------------------------------------------------------------
# no predictable /tmp script
# ---------------------------------------------------------------------------------------------


def test_the_scheduler_wrapper_does_not_write_a_fixed_tmp_script():
    text = WRAPPERS["scheduler"]

    assert not re.search(r"/tmp/version_(check|update)\.py", text), "a fixed /tmp path is still used for the version scripts"
    assert "/var/tmp/bunkerweb/version_" not in text, "/var/tmp/bunkerweb is writable by nginx and cannot hold root-written scripts"
    assert "mktemp -d" in text or "create_private_tmpdir" in text, "the scripts must live in a directory root creates with mktemp -d"


def test_the_private_tmpdir_helper_is_root_owned_readable_and_unpredictable(tmp_path):
    helper = function(source("src/common/helpers/utils.sh"), "create_private_tmpdir")
    script = f'{helper}\nd=$(create_private_tmpdir) || exit 1\nd2=$(create_private_tmpdir) || exit 1\nstat -c "%a %U" "$d"\necho "$d"\necho "$d2"'
    result = bash(script, env={"PATH": os.environ["PATH"], "TMPDIR": str(tmp_path / "elsewhere")})
    try:
        assert result.returncode == 0, result.stderr
        mode, directory, other = result.stdout.splitlines()
        assert mode.split()[0] == "755", f"nginx must be able to read the directory but not write: {mode}"
        assert re.fullmatch(r"/tmp/bunkerweb\.[A-Za-z0-9]{6,}", directory), f"the parent must be the sticky /tmp, whatever TMPDIR says: {directory}"
        assert directory != other, "two calls returned the same directory"
    finally:
        for line in result.stdout.splitlines()[1:]:
            shutil.rmtree(line, ignore_errors=True)


def test_the_scheduler_wrapper_stages_its_scripts_in_that_directory():
    text = WRAPPERS["scheduler"]

    assert "create_private_tmpdir" in text
    assert re.search(r'cat > "\$[A-Za-z_]+/version_check\.py"', text), "version_check.py is not written under the private directory"
    assert re.search(r'cat > "\$[A-Za-z_]+/version_update\.py"', text), "version_update.py is not written under the private directory"
    assert "chmod 644" in text and "chmod 640 /tmp" not in text, "the staged files must be world-readable, not group-writable"
    assert re.search(r"rm -rf -- \"\$[A-Za-z_]+\"", text), "the private directory is never removed"


@pytest.mark.parametrize("name", ["scheduler", "ui", "api"])
def test_each_wrapper_pins_the_interpreter_after_reading_the_env_files(name):
    text = WRAPPERS[name]
    last_export = max(m.start() for m in re.finditer(r"^\s*export_env_file ", text, re.M))
    tail = text[last_export:]

    assert re.search(r"^\s*PYTHON_BIN=\$\(get_python_bin\)", tail, re.M), f"bunkerweb-{name}.sh must re-resolve PYTHON_BIN after export_env_file"
    assert re.search(r'^\s*export PYTHONPATH="\$\{BW_PYTHONPATH\}:', tail, re.M), f"bunkerweb-{name}.sh must re-assert PYTHONPATH after export_env_file"


@pytest.mark.parametrize("name", ["scheduler", "ui", "api"])
def test_an_env_file_cannot_poison_the_pinned_pythonpath(tmp_path, name):
    """`BW_PYTHONPATH` is a plain shell variable: a line for it in an env file must not reach the root PYTHONPATH."""
    text = WRAPPERS[name]
    last_export = max(m.start() for m in re.finditer(r"^\s*export_env_file ", text, re.M))
    pin = re.search(r"^\s*PYTHON_BIN=\$\(get_python_bin\)\n.*?^\s*export PYTHONPATH=[^\n]*\n", text[last_export:], re.M | re.S)
    assert pin, f"bunkerweb-{name}.sh pin block no longer matches"
    env_file = tmp_path / "variables.env"
    env_file.write_text("BW_PYTHONPATH=/tmp/evil\nPYTHONPATH=/tmp/evil2\n", encoding="utf-8")

    result = bash(f'source "{UTILS}"; export_env_file "{env_file}"; {pin.group(0)}\necho "PP=$PYTHONPATH"', env={"PATH": os.environ["PATH"]})

    assert result.returncode == 0, result.stderr
    assert "/tmp/evil" not in result.stdout, f"the env file reached the root PYTHONPATH: {result.stdout!r}"
