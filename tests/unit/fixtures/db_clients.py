"""Database client binaries that `backup_database` and `restore_database` shell out to.

Shared by every test that runs the product's dump or restore, so they all treat a reachable engine
without clients the same way: as a broken environment that FAILS, never a skip.
"""

from shutil import which

# `backup_database` picks its dump binary from the URI's drivername and `restore_database` its
# restore binary the same way, so an engine missing either has nothing to prove here. Each entry is
# the alternative (dump, restore) PAIRS the product accepts: `mysql_client_command` prefers the
# MariaDB client and falls back to the MySQL one, and a host with `mysqldump` but no `mysql` can dump
# and not restore, so the pair has to be checked together rather than binary by binary.
CLIENT_BINARIES = {
    "sqlite": (("sqlite3", "sqlite3"),),
    "postgresql": (("pg_dump", "psql"),),
    "mariadb": (("mariadb-dump", "mariadb"), ("mysqldump", "mysql")),
    "mysql": (("mysqldump", "mysql"), ("mariadb-dump", "mariadb")),
}


def clients_present(db_engine):
    return any(all(which(binary) for binary in pair) for pair in CLIENT_BINARIES[db_engine])


def missing_clients_message(db_engine):
    """The failure text for an engine that answers while none of its client pairs is installed."""
    return (
        f"{db_engine} is reachable but none of its client binaries are installed "
        f"({' / '.join(' + '.join(pair) for pair in CLIENT_BINARIES[db_engine])}); "
        f"backup_database and restore_database shell out to them, so this is a broken environment, not an absent engine"
    )
