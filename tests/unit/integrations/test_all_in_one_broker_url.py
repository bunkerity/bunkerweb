"""The all-in-one broker URL must follow REDIS_SSL, in both places that derive it.

The all-in-one is the one Docker topology whose Celery broker is not a dedicated container: the
entrypoint derives ``CELERY_BROKER_URL`` from ``REDIS_HOST``/``REDIS_PORT`` (``tests/generate.py``
excludes Linux and All-in-one from the ``bw-jobs-broker`` wiring for exactly that reason). Point
``REDIS_*`` at a TLS Redis and the broker followed it -- but the scheme stayed ``redis://``, so the
worker and the API's dispatch client opened a plaintext handshake against a TLS listener. Every
connection came back ``(104, 'Connection reset by peer')``, ``POST /jobs/dispatch`` answered 502 and
the container never went healthy. CI run 32859117306 lost both `core/redis.yml` and
`core/valkey.yml` on the All-in-one arm to it, each at its `tls_check` action.

Two things this guards that a reader would not guess:

* ``healthcheck-all-in-one.sh`` repeats the derivation (a HEALTHCHECK process does not inherit
  supervisord's environment) and its own comment says to keep the two in sync. Fixing only the
  entrypoint leaves ``celery inspect ping`` probing the wrong scheme, which is what actually holds
  the container at "unhealthy".
* ``ssl_cert_reqs`` is always spelled out rather than left to a default, because three clients read
  this one URL and a bare ``rediss://`` does not mean the same thing to all of them. kombu harvests
  every ``ssl_*`` query key into ``conninfo.ssl`` (``kombu/utils/url.py`` ``parse_url``) and
  ``redis.Redis.from_url`` reads them too -- ``worker/tasks.py:_broker_client`` (delivery counter)
  and ``jobs/push-configs.py:_redis_client`` (the push lease). So ``=required`` is what stops kombu
  falling back to ``CERT_NONE`` with "defaulting to insecure SSL behaviour" and silently dropping
  the verification ``REDIS_SSL_VERIFY`` asked for, and ``=none`` -- redundant for kombu, which
  would fall back to ``CERT_NONE`` anyway -- is what stops the two redis-py consumers failing
  ``CERTIFICATE_VERIFY_FAILED`` against a private CA while the worker itself is happily connected.

The block is executed rather than string-matched: a guard that greps for ``rediss`` would pass on a
fix that emits it in the wrong branch.
"""

from pathlib import Path
from subprocess import run

import pytest

ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = ROOT.joinpath("src", "all-in-one", "entrypoint.sh")
HEALTHCHECK = ROOT.joinpath("src", "common", "helpers", "healthcheck-all-in-one.sh")

# Where each script's derivation starts and ends. Both build the same URL from the same
# variables; only the indentation, the local names and the "don't clobber an explicit value"
# mechanism differ -- the entrypoint uses `${CELERY_BROKER_URL:-...}` inline, the healthcheck
# wraps the whole block in `if [ -z ... ]`. BOTH anchors are lines that actually ship, so the
# guard is executed rather than synthesized: an earlier version re-created the healthcheck's
# `if [ -z ... ]` here, and deleting the real one from the script left this test green.
BLOCKS = {
    "entrypoint": (ENTRYPOINT, '\t_broker_credentials=""', None),
    "healthcheck": (HEALTHCHECK, '  if [ -z "${CELERY_BROKER_URL:-}" ]; then', "\n  fi\n"),
}


def _locate(text: str, needle: str, start: int, which: str, what: str) -> int:
    """`str.index` with an error that names the anchor. A moved anchor must fail, never silently
    shrink the slice to something that still runs."""
    try:
        return text.index(needle, start)
    except ValueError:
        raise ValueError(f"{which}: {what} anchor {needle!r} no longer appears in the script -- update this test with the code it guards") from None


def derive(which: str, env: dict) -> str:
    """Run the real derivation block out of the shipped script and return the URL it exports."""
    path, start, close = BLOCKS[which]
    text = path.read_text(encoding="utf-8")
    begin = _locate(text, start, 0, which, "start")
    export = _locate(text, "export CELERY_BROKER_URL", begin, which, "export")
    if close is None:
        # No wrapper: the slice ends with the export line itself.
        stop = _locate(text, "\n", export, which, "end-of-export")
    else:
        # Include the `fi` that closes the shipped `if [ -z ... ]`. It is the first one at the
        # wrapper's own indentation after the export -- the nearer `fi`s close inner branches.
        stop = _locate(text, close, export, which, "close") + len(close)
    script = f"{text[begin:stop]}\nprintf '%s' \"${{CELERY_BROKER_URL}}\"\n"
    proc = run(["bash", "-c", script], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", **env})
    assert proc.returncode == 0, f"{which} block failed: {proc.stderr}"
    return proc.stdout


CASES = [
    # (env, expected URL)
    ({}, "redis://127.0.0.1:6379/0"),
    ({"REDIS_HOST": "valkey", "REDIS_PORT": "6380"}, "redis://valkey:6380/0"),
    # The regression: REDIS_SSL=yes has to move the scheme, not just the port.
    ({"REDIS_HOST": "valkey", "REDIS_PORT": "6380", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no"}, "rediss://valkey:6380/0?ssl_cert_reqs=none"),
    # REDIS_SSL_VERIFY left at its product default (yes) must SAY `required`. A bare `rediss://`
    # is not equivalent: kombu logs "defaulting to insecure SSL behaviour" and uses CERT_NONE,
    # so omitting it silently discards the verification the operator did not opt out of.
    ({"REDIS_HOST": "redis-master", "REDIS_PORT": "6379", "REDIS_SSL": "yes"}, "rediss://redis-master:6379/0?ssl_cert_reqs=required"),
    # ... and stating it explicitly is the same URL.
    (
        {"REDIS_HOST": "redis-master", "REDIS_PORT": "6379", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "yes"},
        "rediss://redis-master:6379/0?ssl_cert_reqs=required",
    ),
    # REDIS_SSL_VERIFY alone must not turn TLS on, and must not leak a query onto a plain URL.
    ({"REDIS_HOST": "valkey", "REDIS_SSL_VERIFY": "no"}, "redis://valkey:6379/0"),
    ({"REDIS_HOST": "valkey", "REDIS_SSL_VERIFY": "yes"}, "redis://valkey:6379/0"),
    # The password keeps travelling in the URL, TLS or not.
    (
        {"REDIS_HOST": "valkey", "REDIS_PORT": "6380", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no", "REDIS_PASSWORD": "secret"},
        "rediss://:secret@valkey:6380/0?ssl_cert_reqs=none",
    ),
]


@pytest.mark.parametrize("which", sorted(BLOCKS))
@pytest.mark.parametrize("env,expected", CASES, ids=[str(i) for i in range(len(CASES))])
def test_broker_url_follows_redis_ssl(which, env, expected):
    assert derive(which, env) == expected


def test_an_explicit_broker_url_still_wins():
    """An operator who sets CELERY_BROKER_URL owns it -- REDIS_SSL must not rewrite it."""
    for which in BLOCKS:
        env = {"CELERY_BROKER_URL": "redis://someone-elses-broker:6379/3", "REDIS_SSL": "yes", "REDIS_HOST": "valkey"}
        assert derive(which, env) == "redis://someone-elses-broker:6379/3"


def test_both_scripts_agree_on_every_case():
    """The two derivations are duplicated by necessity; nothing but this test keeps them equal."""
    for env, _ in CASES:
        assert derive("entrypoint", env) == derive("healthcheck", env), env
