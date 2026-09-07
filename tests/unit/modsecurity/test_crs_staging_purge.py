"""The CRS staging tree must be purged before it is consulted.

`download-crs-plugins.py` builds each plugin into `NEW_PLUGINS_DIR/<plugin_id>` file by file,
then swaps the whole tree over the live `CRS_PLUGINS_DIR`. Two facts combine badly:

* the loop treats the mere *existence* of `NEW_PLUGINS_DIR/<plugin_id>` as "already extracted,
  skipping", and
* the cleanup that removes the staging tree only runs on a clean exit.

So a run killed midway through copying one plugin left a directory holding, say, only
`<name>-config.conf`; the next run adopted it as complete, copied it over the live tree and
cached it in the database. Every service using that plugin then included its config with none of
its rule files behind it — and the state persisted, because the next run adopted it again.

The purge is a statement in the script body rather than a function, and the module is a script
that runs (and downloads) on import, so the reachable property is the ORDERING: the staging tree
is discarded before anything reads it. That is exactly what the fix is.
"""

from pathlib import Path
from re import search

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "modsecurity" / "jobs" / "download-crs-plugins.py"
SOURCE = JOB_PATH.read_text(encoding="utf-8")

PURGE = "rmtree(NEW_PLUGINS_DIR, ignore_errors=True)"
ADOPTION_CHECK = "if NEW_PLUGINS_DIR.joinpath(plugin_id).is_dir():"


def test_the_staging_tree_is_purged_at_the_start_of_a_run():
    assert PURGE in SOURCE


def test_the_purge_happens_before_anything_adopts_a_staged_directory():
    """Ordering is the whole property: purging after the adoption check would be useless, and
    the end-of-run cleanup (which already existed) is exactly that useless case."""
    assert ADOPTION_CHECK in SOURCE, "the adoption check moved — this test is measuring nothing"

    first_purge = SOURCE.index(PURGE)
    adoption = SOURCE.index(ADOPTION_CHECK)

    assert first_purge < adoption


def test_the_end_of_run_cleanup_is_still_there():
    """The start-of-run purge is a second line of defence, not a replacement: a clean run should
    still leave nothing behind rather than relying on the next run to tidy up."""
    assert SOURCE.rindex(PURGE) > SOURCE.index(ADOPTION_CHECK)


# --- the live tree must survive the run intact ---------------------------------------------------
# Ported with dev `a92cc3187`. `plugin_failures` makes a partial run keep the PREVIOUS plugin set,
# but "keep it" is only true if nothing emptied it first. The reuse branch used to `move()` an
# already-installed plugin out of CRS_PLUGINS_DIR into the staging tree, so by the time a later
# plugin failed, the set being "kept" had already lost every plugin the loop had reused. Like the
# purge above, this is a statement in the script body, so the reachable property is the source.
REUSE_BRANCH = "elif CRS_PLUGINS_DIR.joinpath(plugin_id, plugin_config.name).is_file():"


def test_an_already_installed_plugin_is_copied_out_of_the_live_tree_not_moved():
    assert REUSE_BRANCH in SOURCE, "the reuse branch moved -- this test is measuring nothing"

    branch = SOURCE.index(REUSE_BRANCH)
    body = SOURCE[branch : SOURCE.index("NEW_PLUGINS_DIR.joinpath(plugin_id).mkdir(", branch)]  # noqa: E203

    assert "copytree(CRS_PLUGINS_DIR.joinpath(plugin_id)" in body
    assert "move(" not in body, "moving out of CRS_PLUGINS_DIR empties the set the failure guard keeps"


def test_the_job_can_no_longer_move_anything_at_all():
    """`shutil.move` has no remaining caller, and dropping the import is what keeps it that way:
    a re-introduced `move(...)` NameErrors instead of quietly emptying the live tree again.
    (A substring scan for `move(` cannot do this job -- `plugins.remove(plugin)` contains it.)"""
    assert "from shutil import copy, copytree, rmtree" in SOURCE
    assert not search(r"\bmove\(", SOURCE)
