r"""A preserved configuration is never kept when its install was interrupted.

With `KEEP_CONFIG_ON_RESTART=yes` the start script keeps the rendered `/etc/nginx` and only asks the
scheduler for the latest push. An install cut short leaves a tree mixing two generations, and keeping it
left the instance serving a half-written configuration. The installer now drops
`/etc/nginx/.bw-install-incomplete` first and removes it once done, so the start scripts must regenerate
the temporary configuration when that sentinel is present, refuse to start when generation fails, and
keep the normal keep-config path (marker for the scheduler, no regeneration) when it is absent.

The decision block, `render_temp_config` and its call site are lifted from `src/bw/entrypoint.sh` (Docker)
and `src/linux/scripts/start.sh` (Linux) and run against a temp root with a recording generator stub.
"""

import pytest
from _t7_helpers import block, bash, function, retarget, source

SCRIPTS = {
    "docker": {
        "path": "src/bw/entrypoint.sh",
        "call": r'^\s*if \[\[ "\$regenerate_temp_config" == "true" \]\] ; then\n\s*render_temp_config \|\| exit 1\n\s*fi\n',
        "stubs": 'python3() { echo "python3 $*" >> "$CALLS"; return "${GEN_RC:-0}"; }\nPYTHON_BIN=python3',
    },
    "linux": {
        "path": "src/linux/scripts/start.sh",
        "call": r'^\s*if \[\[ "\$regenerate_temp_config" == "true" \]\] ; then\n\s*render_temp_config \|\| exit 1\n\s*fi\n',
        "stubs": (
            'run_as_nginx() { if [ "$1" = touch ]; then "$@"; else echo "gen $*" >> "$CALLS"; return "${GEN_RC:-0}"; fi; }\n'
            "PYTHON_BIN=python3\nBW_PYTHONPATH=''"
        ),
    },
}
DECISION = r"^\s*install_sentinel=.*?^\s*fi\n(?=\n\s*(?:printf|write_tmp_env_file))"
HARNESS = """
CALLS="{root}/calls"
: > "$CALLS"
log() {{ echo "$*" >&2; }}
{stubs}
tmp_env_path="{root}/var/tmp/tmp.env"
KEEP_CONFIG_ON_RESTART="{keep}"
regenerate_temp_config=false
{render}
{decision}
{call}
echo reached-end
"""


def _run(tmp_path, variant, *, keep="yes", sentinel=False, gen_rc=0, tmp_env=True):
    spec = SCRIPTS[variant]
    text = source(spec["path"])
    prefixes = ("/etc/nginx", "/var/tmp", "/usr/share/bunkerweb")
    script = HARNESS.format(
        root=tmp_path,
        stubs=spec["stubs"],
        keep=keep,
        render=retarget(function(text, "render_temp_config"), tmp_path, *prefixes),
        decision=retarget(block(text, DECISION, "the keep-config decision"), tmp_path, *prefixes),
        call=block(text, spec["call"], "the regenerate call site"),
    )
    (tmp_path / "etc/nginx").mkdir(parents=True)
    (tmp_path / "var/tmp").mkdir(parents=True)
    if tmp_env:
        (tmp_path / "var/tmp/tmp.env").write_text("HTTP_PORT=8080\n", encoding="utf-8")
    if sentinel:
        (tmp_path / "etc/nginx/.bw-install-incomplete").write_text("", encoding="utf-8")
    result = bash(script, env={"PATH": "/usr/bin:/bin", "GEN_RC": str(gen_rc)})
    calls = (tmp_path / "calls").read_text(encoding="utf-8").splitlines()
    return result, calls


@pytest.mark.parametrize("variant", SCRIPTS)
def test_an_interrupted_install_is_regenerated_not_kept(tmp_path, variant):
    result, calls = _run(tmp_path, variant, sentinel=True)

    assert result.returncode == 0, result.stderr
    assert len(calls) == 1 and "--variables" in calls[0], f"the temporary config was not regenerated: {calls}"
    assert not (tmp_path / "etc/nginx/.bw-install-incomplete").exists(), "the sentinel outlived the regeneration"
    assert not (tmp_path / "var/tmp/bunkerweb_needs_config").exists(), "a regenerated config must not ask the scheduler to replace a kept one"


@pytest.mark.parametrize("variant", SCRIPTS)
def test_a_complete_install_is_still_preserved(tmp_path, variant):
    """Anti-vacuity: without the sentinel the keep-config path must be untouched, so the test above
    cannot pass merely because everything is regenerated."""
    result, calls = _run(tmp_path, variant, sentinel=False)

    assert result.returncode == 0, result.stderr
    assert calls == [], f"a complete preserved config was regenerated: {calls}"
    assert (tmp_path / "var/tmp/bunkerweb_needs_config").exists(), "the scheduler was not asked for the latest config"


@pytest.mark.parametrize("variant", SCRIPTS)
def test_a_failed_generation_refuses_to_start_and_keeps_the_sentinel(tmp_path, variant):
    result, calls = _run(tmp_path, variant, sentinel=True, gen_rc=1)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "reached-end" not in result.stdout
    assert len(calls) == 1, calls
    assert (tmp_path / "etc/nginx/.bw-install-incomplete").exists(), "the sentinel was cleared although nothing was regenerated"
