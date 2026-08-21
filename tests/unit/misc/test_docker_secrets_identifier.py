"""A Docker secret whose filename is not a shell identifier must be skipped, not exported.

`handle_docker_secrets` (src/common/helpers/utils.sh) exports every file in /run/secrets as an
environment variable named after the file, uppercased. The natural name for a certificate secret is
`example.com.key`, which uppercases to `EXAMPLE.COM.KEY` — and `export` refuses that, as it refuses
any name with a dot or a dash (`db-password`). Two consequences, one loud and one silent:

* `src/worker/entrypoint.sh` is the one entrypoint of seven that runs `set -e`, so the failed
  `export` killed **bw-worker** at boot. Found exactly that way: mounting a Swarm secret named
  `secret.example.com.key` on bw-worker crash-looped it with `task: non-zero exit (1)`.
* In **all seven** entrypoints, `export` prints the rejected assignment to stderr — so the secret's
  own contents were written into the container's log, while the container went on looking healthy.
  That is the worse half, and it is the half a boot-crash test would not have caught.

These tests drive the real function in a real bash, so they fail against the real defect rather
than against a reimplementation of it. `BW_DOCKER_SECRETS_DIR` exists for this: it is the only hook
the fix added, and nothing in a deployment sets it.

Nothing here is skipped and nothing needs a container: bash is the only requirement.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src" / "common" / "helpers" / "utils.sh"

PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ\n-----END PRIVATE KEY-----"


def _run(secrets, *, set_e=True, dump=()):
    """Source utils.sh in a real bash, run handle_docker_secrets over a temp secrets dir.

    `set_e` mirrors src/worker/entrypoint.sh, the one entrypoint that has it — which is why the
    boot crash was worker-only.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for name, value in secrets.items():
            (directory / name).write_text(value)

        dumps = "".join(f'echo "DUMP {v}=${{{v}-<unset>}}";' for v in dump)
        script = f"""
        {'set -e' if set_e else ''}
        source '{UTILS}'
        handle_docker_secrets
        {dumps}
        echo "REACHED_END"
        """
        completed = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "BW_DOCKER_SECRETS_DIR": str(directory)},
        )
        return completed


def test_a_secret_named_like_a_certificate_does_not_kill_the_entrypoint():
    """The boot crash. Under `set -e`, as src/worker/entrypoint.sh runs.

    Mutant: remove the `[[ ... =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]` guard — the export fails, `set -e`
    fires, REACHED_END never prints and the return code is non-zero.
    """
    result = _run({"example.com.key": PRIVATE_KEY}, set_e=True)

    assert result.returncode == 0, f"the entrypoint died on a dotted secret name: {result.stderr}"
    assert "REACHED_END" in result.stdout, "execution stopped before the end of the entrypoint"


def test_a_dashed_secret_name_is_also_survivable():
    """`db-password` is at least as likely as a certificate name, and `-` is equally invalid."""
    result = _run({"db-password": "hunter2"}, set_e=True)

    assert result.returncode == 0, result.stderr
    assert "REACHED_END" in result.stdout


def test_the_secret_value_never_reaches_the_output():
    """The silent half, and the one that matters in the six entrypoints WITHOUT `set -e`: a failed
    `export` prints the whole rejected assignment, so the private key was written to the container
    log while the container carried on. Checked on stdout and stderr together.

    Mutant: remove the guard — bash prints
    `export: `EXAMPLE.COM.KEY=-----BEGIN PRIVATE KEY-----...': not a valid identifier`.
    """
    result = _run({"example.com.key": PRIVATE_KEY}, set_e=False)

    combined = result.stdout + result.stderr
    assert "BEGIN PRIVATE KEY" not in combined, f"the secret's contents were logged: {combined}"
    assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ" not in combined


def test_the_skip_is_reported_and_names_the_file():
    """Skipping in silence would be its own defect: the operator has to learn the secret is there
    but not in the environment. The message names the FILE and must not name the value."""
    result = _run({"example.com.key": PRIVATE_KEY}, set_e=False)

    combined = result.stdout + result.stderr
    assert "example.com.key" in combined, f"the skipped secret was not reported: {combined}"
    assert "Skipped Docker secret" in combined


def test_a_valid_name_is_still_exported():
    """RULE 19 floor. A guard that skipped everything would pass every test above."""
    result = _run({"api_token": "s3cr3t"}, set_e=True, dump=("API_TOKEN",))

    assert result.returncode == 0, result.stderr
    assert "DUMP API_TOKEN=s3cr3t" in result.stdout, f"a valid secret stopped being exported: {result.stdout}"


def test_a_valid_secret_beside_an_invalid_one_is_still_exported():
    """The real shape: a stack with several secrets, one of them a certificate. `continue`, not
    `return` — an early return would drop every secret sorted after the bad one, which is a
    filename-ordering-dependent failure and the nastiest possible regression here."""
    result = _run(
        {"aaa_first": "one", "example.com.key": PRIVATE_KEY, "zzz_last": "two"},
        set_e=True,
        dump=("AAA_FIRST", "ZZZ_LAST"),
    )

    assert result.returncode == 0, result.stderr
    assert "DUMP AAA_FIRST=one" in result.stdout
    assert "DUMP ZZZ_LAST=two" in result.stdout, "a secret sorted after the invalid one was dropped"


def test_the_override_defaults_to_the_real_docker_path():
    """`BW_DOCKER_SECRETS_DIR` is a test hook, so the default must still be /run/secrets — if it
    drifted, every test above would pass while production read nothing at all."""
    assert 'local secrets_dir="${BW_DOCKER_SECRETS_DIR:-/run/secrets}"' in UTILS.read_text(encoding="utf-8")
