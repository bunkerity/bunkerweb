"""``zerossl-bot.sh`` takes the ZeroSSL API key from its environment, never from a command-line argument.

The wrapper used to accept ``--zerossl-api-key`` (and ``-z``), which put the key in the process list of the job that launched
it and in certbot's own arguments. The key now comes only from ``LETS_ENCRYPT_ZEROSSL_API_KEY`` and is removed from the
environment before certbot starts. This runs the real script in bash with stand-ins for ``curl`` and ``certbot`` (no network)
and pins what each of them receives. Refs: #3237.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "src" / "common" / "core" / "letsencrypt" / "lib" / "zerossl-bot.sh"
BASH = shutil.which("bash") or "/bin/bash"

pytestmark = pytest.mark.skipif(shutil.which("python3") is None, reason="the script parses the ZeroSSL answer with python3")

CURL_STUB = r"""#!/bin/bash
{ printf 'ARGV:'; printf ' [%s]' "$@"; echo; } >> "$CURL_LOG"
prev=""
for arg in "$@"; do
    if [ "$prev" = "--config" ]; then echo "CONFIG: $(cat "$arg")" >> "$CURL_LOG"; fi
    prev="$arg"
done
printf '%s\n200' '{"eab_kid":"kid-1","eab_hmac_key":"hmac-1"}'
"""

CERTBOT_STUB = r"""#!/bin/bash
printf '%s\n' "$@" > "$STUB_CERTBOT_ARGV"
env > "$CERTBOT_ENV"
"""

API_KEY = "zs-api-key-from-env"
ARG_KEY = "zs-api-key-from-argv"


def executable(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.fixture
def run(tmp_path):
    stubs = tmp_path / "bin"
    stubs.mkdir()
    executable(stubs / "curl", CURL_STUB)
    certbot = executable(tmp_path / "certbot", CERTBOT_STUB)
    curl_log, certbot_args, certbot_env = tmp_path / "curl.log", tmp_path / "certbot.args", tmp_path / "certbot.env"

    def go(*args: str, **env: str):
        full = {
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "CERTBOT_BIN": str(certbot),
            "CURL_LOG": str(curl_log),
            "STUB_CERTBOT_ARGV": str(certbot_args),
            "CERTBOT_ENV": str(certbot_env),
            **env,
        }
        done = subprocess.run([BASH, str(SCRIPT), *args], capture_output=True, text=True, env=full, timeout=30, check=False)
        read = lambda path: path.read_text(encoding="utf-8") if path.exists() else ""  # noqa: E731
        return done, read(curl_log), read(certbot_args).splitlines(), read(certbot_env)

    return go


def test_the_api_key_in_the_environment_fetches_the_eab_credentials_and_never_reaches_a_process_argument(run):
    done, curl_log, certbot_args, _ = run("certonly", "-d", "example.com", LETS_ENCRYPT_ZEROSSL_API_KEY=API_KEY)
    assert done.returncode == 0, done.stderr
    assert f'CONFIG: url = "https://api.zerossl.com/acme/eab-credentials?access_key={API_KEY}"' in curl_log
    assert curl_log.count("ARGV:") == 1
    assert API_KEY not in "".join(line for line in curl_log.splitlines() if line.startswith("ARGV:"))
    assert certbot_args[:4] == ["certonly", "-d", "example.com", "--eab-kid"]
    assert certbot_args[4:] == ["kid-1", "--eab-hmac-key", "hmac-1", "--server", "https://acme.zerossl.com/v2/DV90"]
    assert API_KEY not in certbot_args


def test_certbot_does_not_inherit_the_api_key_in_its_environment(run):
    done, _, _, certbot_env = run("certonly", LETS_ENCRYPT_ZEROSSL_API_KEY=API_KEY)
    assert done.returncode == 0, done.stderr
    assert certbot_env, "the certbot stand-in did not run"
    assert "LETS_ENCRYPT_ZEROSSL_API_KEY" not in certbot_env
    assert API_KEY not in certbot_env


@pytest.mark.parametrize("flag", [[f"--zerossl-api-key={ARG_KEY}"], ["--zerossl-api-key", ARG_KEY], ["-z", ARG_KEY]])
def test_an_api_key_given_as_an_argument_is_never_used_to_call_the_zerossl_api(run, flag):
    done, curl_log, _, _ = run("certonly", *flag)
    assert done.returncode == 0, done.stderr
    assert ARG_KEY not in curl_log
    assert curl_log == "", "an argument must not trigger the API key flow"
