"""Publishing the CRS plugin set must not go through the live directory.

`swap_and_cache_plugins` used to `rmtree(CRS_PLUGINS_DIR)` and then `copytree()` this run's staging
tree over it. Anything that interrupted the copy -- a full disk, a killed process, an unreadable
staged file -- left ModSecurity with a PARTIAL plugin set, and the rendered configuration is the
intersection of that directory and `crs-plugins.json`, so the missing plugins silently stopped being
enforced while the job reported nothing.

Port of dev `63a7f6a4d`: the set is staged in a sibling directory and renamed into place.
"""

from unittest.mock import MagicMock

import pytest

from crs_plugins_job_source import load_job_helpers


@pytest.fixture
def swap(tmp_path):
    """`swap_and_cache_plugins` wired to temporary directories, with a live previous plugin set."""
    namespace = load_job_helpers()
    previous = tmp_path / "crs"
    staging = tmp_path / "new"
    (previous / "plugin-a-1.0").mkdir(parents=True)
    (previous / "plugin-a-1.0" / "plugin.conf").write_text("SecRule previous\n")
    (staging / "plugin-b-1.0").mkdir(parents=True)
    (staging / "plugin-b-1.0" / "plugin.conf").write_text("SecRule fresh\n")

    job = MagicMock()
    job.cache_hash.return_value = b""
    job.cache_file.return_value = (True, "")
    job.cache_dir.return_value = (True, "")

    namespace["CRS_PLUGINS_DIR"] = previous
    namespace["NEW_PLUGINS_DIR"] = staging
    namespace["JOB"] = job
    namespace["status"] = 0
    return namespace, previous, job


def test_an_interrupted_copy_leaves_the_previous_plugin_set_in_place(swap):
    """The regression: the live directory was wiped before the new set was known to be complete."""
    namespace, previous, job = swap

    def _explode(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    namespace["copytree"] = _explode

    with pytest.raises(OSError):
        namespace["swap_and_cache_plugins"]({"svc": {"https://example.invalid/b.zip"}}, False)

    assert (previous / "plugin-a-1.0" / "plugin.conf").read_text() == "SecRule previous\n", "an interrupted publication destroyed the live plugin set"
    job.cache_file.assert_not_called()
    job.cache_dir.assert_not_called()


def test_a_completed_publication_leaves_no_staging_artifact(swap):
    """The rollback machinery must clean up after itself, or the next run rolls back a good set."""
    namespace, previous, _ = swap

    namespace["swap_and_cache_plugins"]({"svc": {"https://example.invalid/b.zip"}}, False)

    assert sorted(p.name for p in previous.iterdir()) == ["plugin-b-1.0"]
    assert not list(previous.parent.glob(".crs.cache-*")), "the publication left a backup, journal or staging directory behind"
