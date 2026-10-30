"""An upgrade from 1.6.11~rc1 aborted the scheduler because that prerelease had no migration file.

``entrypoint.sh`` turns the version stored in ``bw_metadata`` into a revision by globbing
``*_upgrade_to_version_<version>.py``; a prerelease without its own file gives it nothing to stamp, so it
logged "No migration file found for database version" and the scheduler never started. 1.6.11~rc1 now has a
migration in every engine directory, and the 1.6.11 migration follows it. The test resolves the version the
way the entrypoint does and walks the chain.
"""

import pytest

from alembic_baseline import chain, revision_for

ENGINES = ("sqlite", "mariadb", "mysql", "postgresql")


@pytest.mark.parametrize("engine", ENGINES)
def test_a_database_recorded_at_1_6_11_rc1_resolves_to_a_revision(engine):
    assert revision_for("1.6.11~rc1", engine)


@pytest.mark.parametrize("engine", ENGINES)
def test_the_1_6_11_migration_follows_the_rc1_migration_which_follows_1_6_10(engine):
    links = chain(engine)
    rc1 = revision_for("1.6.11~rc1", engine)
    final = revision_for("1.6.11", engine)
    previous = revision_for("1.6.10", engine)

    assert links[final][0] == rc1
    assert links[rc1][0] == previous
