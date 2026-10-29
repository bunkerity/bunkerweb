r"""The all-in-one entrypoint creates Redis' data directory before Redis is enabled.

On a first start with a fresh `/data` volume the local Redis could not start: `/var/lib/redis` points into
`/data/redis`, which did not exist yet. The entrypoint now creates the directory (following the symlink),
gives it the build-time mode `770` and hands it to nginx, and exits when it cannot. The block is lifted from
`src/all-in-one/entrypoint.sh` and run against a temp root with a recording `chown`.

Refs #2556.
"""

from _t7_helpers import bash, block, retarget, source

LIFTED = block(source("src/all-in-one/entrypoint.sh"), r"^# Ensure Redis data directory exists.*?^fi\n", "the Redis data directory block")


def _run(tmp_path, *, use_redis="yes", link_to=None, blocked=False):
    lib = tmp_path / "var/lib"
    lib.parent.mkdir(parents=True)
    if blocked:
        lib.write_text("not a directory", encoding="utf-8")  # mkdir -p below it must fail
    else:
        lib.mkdir()
    if link_to is not None:
        (lib / "redis").symlink_to(link_to)
    script = 'log() { echo "$*" >&2; }\nchown() { echo "$*" >> "%s/chowns"; }\nUSE_REDIS=%s\n%s\necho done\n' % (
        tmp_path,
        use_redis,
        retarget(LIFTED, tmp_path, "/var/lib/redis"),
    )
    return bash(script, env={"PATH": "/usr/bin:/bin"})


def test_a_fresh_data_volume_gets_the_directory_behind_the_symlink(tmp_path):
    target = tmp_path / "data/redis"

    result = _run(tmp_path, link_to=target)

    assert result.returncode == 0, result.stderr
    assert target.is_dir(), "the dangling symlink target was not created"
    assert target.stat().st_mode & 0o777 == 0o770
    assert (tmp_path / "chowns").read_text(encoding="utf-8").split() == ["nginx:nginx", str(target)]


def test_a_plain_missing_directory_is_created(tmp_path):
    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "var/lib/redis").is_dir()


def test_nothing_is_created_when_the_local_redis_is_off(tmp_path):
    """Anti-vacuity: the directory is only wanted when the all-in-one Redis is enabled."""
    result = _run(tmp_path, use_redis="no", link_to=tmp_path / "data/redis")

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "data/redis").exists()


def test_a_directory_that_cannot_be_created_stops_the_container(tmp_path):
    result = _run(tmp_path, blocked=True)

    assert result.returncode == 1, result.stdout
    assert "done" not in result.stdout
    assert "Failed to create Redis data directory" in result.stderr
