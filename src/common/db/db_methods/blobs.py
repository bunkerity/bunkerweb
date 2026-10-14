#!/usr/bin/env python3
"""Large-blob chunking for the three binary columns that can outgrow one statement (#3965).

A MySQL/MariaDB statement cannot carry more than ``max_allowed_packet`` bytes, and a non-SUPER
user cannot raise it, so a plugin archive, a plugin page or a job cache that big failed with
"MySQL server has gone away". Such a blob is stored in ``bw_blob_chunks`` instead, and the owner's
own ``data`` column holds ``BLOB_CHUNK_MARKER`` followed by the sha256 of the whole blob.

A column value is a reference only when it has exactly that shape (``_blob_reference``). Data that
merely starts with the marker (an external list can hold anything) is never stored inline, so
every reference ever written by this code was written as a reference; any other value is data.

These are plain functions that take the caller's session, never a mixin: a mixin method would open
its own ``_db_session``, which is not reentrant (it would close the session the caller holds), and
``delete_service_rows`` is a module function with no ``self``.

Only ``Plugins.data``, ``Plugin_pages.data`` and ``Jobs_cache.data`` are chunked, and only on
MySQL/MariaDB: PostgreSQL and SQLite have no practical limit, so ``blob_chunk_size`` is ``None``
there and nothing is written to ``bw_blob_chunks`` in production, except data that starts with
``BLOB_CHUNK_MARKER`` (see above).

Owner keys: ``bw_plugins:<plugin id>``, ``bw_plugin_pages:<plugin id>`` and ``bw_jobs_cache:<row id>``.
The job-cache key is the row id, not the (job, service, file) triple, so renaming a service
re-keys ``service_id`` without moving the chunks. The chunk table has no foreign key (the owner is
a string), so no engine cascades into it: every path that deletes an owner row calls
``blob_sweep`` before it commits.
"""

from hashlib import sha256
from logging import Logger
from typing import Any, Callable, Optional

from model import Blob_chunks, Jobs_cache, Plugin_pages, Plugins  # type: ignore

from sqlalchemy import and_, bindparam, func, select, text

# 16 bytes, then the 64 hex characters of the sha256: an 80 byte value in the owner's column.
BLOB_CHUNK_MARKER = b"\x00bw-blob-chunks\x00"
BLOB_CHUNK_MAX = 4 * 1024 * 1024
BLOB_CHUNK_MIN = 16 * 1024
BLOB_MARKER_LENGTH = len(BLOB_CHUNK_MARKER) + 64
_HEX_DIGITS = frozenset(b"0123456789abcdef")
# Attempts a reader makes when a writer swaps the chunk set between its marker read and its chunk read.
BLOB_LOAD_ATTEMPTS = 3
# Ids per IN (...) while sweeping: SQLite caps bound parameters per statement.
_SWEEP_BATCH = 500


def chunk_size_for(dialect: str, max_allowed_packet: int) -> Optional[int]:
    """Largest blob one statement can carry for ``dialect``, or ``None`` when there is no practical limit.

    PyMySQL >= 1.2.1 sends bytes as a hex literal, so a blob costs twice its size on the wire, plus
    the statement's own text: a third of the packet, less 64 KiB of headroom, is safe."""
    if dialect not in ("mysql", "mariadb"):
        return None
    return max(BLOB_CHUNK_MIN, min(BLOB_CHUNK_MAX, (max_allowed_packet - 64 * 1024) // 3))


def blob_chunk_size(session: Any) -> Optional[int]:
    """``chunk_size_for`` the backend the session is bound to (reads ``@@max_allowed_packet`` on MySQL/MariaDB)."""
    dialect = session.get_bind().dialect.name
    if dialect not in ("mysql", "mariadb"):
        return None
    return chunk_size_for(dialect, int(session.execute(text("SELECT @@max_allowed_packet")).scalar()))


def _blob_reference(value: Optional[bytes]) -> Optional[str]:
    """The checksum a column value references, or ``None`` when the value is plain data.

    The one place that tells the two apart: exactly the marker and 64 lowercase hex characters.
    The suffix is checked as bytes, never decoded first.

    ponytail: an inline value written before this check that is byte-identical to a well-formed
    reference still resolves as one (missing chunks read as ``None`` with an error log): the two are
    indistinguishable once stored. Nothing written since can collide, see ``blob_store``."""
    if value is None or len(value) != BLOB_MARKER_LENGTH or not value.startswith(BLOB_CHUNK_MARKER):
        return None
    suffix = value[len(BLOB_CHUNK_MARKER) :]
    return suffix.decode() if _HEX_DIGITS.issuperset(suffix) else None


def blob_matches(value: Optional[bytes], data: Optional[bytes]) -> bool:
    """Compare a stored column value, reference or not, with plain data."""
    checksum = _blob_reference(value)
    if checksum is not None:
        return data is not None and checksum == sha256(data).hexdigest()
    return value == data


def blob_drop(session: Any, *conditions: Any) -> None:
    """Delete chunk rows one primary key at a time, after a non-locking look for them.

    A ranged DELETE takes next-key locks and, under MariaDB's snapshot isolation, fails with error
    1020 as soon as a concurrent job has touched a neighbouring chunk row."""
    keys = [
        {"o": row.owner, "c": row.checksum, "i": row.idx}
        for row in session.execute(select(Blob_chunks.owner, Blob_chunks.checksum, Blob_chunks.idx).where(*conditions))
    ]
    if keys:
        table = Blob_chunks.__table__
        session.execute(table.delete().where(and_(table.c.owner == bindparam("o"), table.c.checksum == bindparam("c"), table.c.idx == bindparam("i"))), keys)


def blob_store(session: Any, owner: str, data: Optional[bytes]) -> Optional[bytes]:
    """Return what to write in the owner's data column.

    The data itself when it fits one statement, otherwise a marker with the data going to
    ``bw_blob_chunks``, one row per statement. Data that starts with the marker always goes there,
    on every engine, so an inline value is never mistaken for a reference. The owner's other chunk
    sets are dropped in the same transaction, so a reader sees the old blob or the new one, never a mix."""
    size = blob_chunk_size(session)
    value = data
    checksum = ""
    if data is not None and (data.startswith(BLOB_CHUNK_MARKER) or (size and len(data) > size)):
        size = size or BLOB_CHUNK_MAX
        checksum = sha256(data).hexdigest()
        value = BLOB_CHUNK_MARKER + checksum.encode()
        if session.execute(select(Blob_chunks.idx).filter_by(owner=owner, checksum=checksum).limit(1)).first() is None:
            for idx, start in enumerate(range(0, len(data), size)):
                session.add(Blob_chunks(owner=owner, checksum=checksum, idx=idx, data=data[start : start + size]))
                # One chunk per statement: MariaDB batches pending INSERTs ... RETURNING into one packet otherwise.
                session.flush()
    blob_drop(session, Blob_chunks.owner == owner, Blob_chunks.checksum != checksum)
    return value


def blob_load(
    session: Any,
    owner: str,
    value: Optional[bytes],
    logger: Logger,
    reread: Optional[Callable[[], Optional[bytes]]] = None,
) -> Optional[bytes]:
    """Resolve a data column value: plain data is returned as is, a reference is reassembled from its chunks.

    A writer may commit between the read of the marker and the read of the chunks (READ COMMITTED on
    PostgreSQL, autocommit reads on SQLite), leaving the old chunk set gone. ``reread`` fetches the
    owner's column again so the newer marker is followed instead. ``None`` (and an error in the
    log) when the chunks are missing or do not hash to the marker."""
    for _ in range(BLOB_LOAD_ATTEMPTS):
        checksum = _blob_reference(value)
        if checksum is None:
            return value
        data = b"".join(row.data for row in session.execute(select(Blob_chunks.data).filter_by(owner=owner, checksum=checksum).order_by(Blob_chunks.idx)))
        if sha256(data).hexdigest() == checksum:
            return data
        if reread is None:
            break
        value = reread()
    logger.error(f"Stored blob {owner} is incomplete, its chunks are missing or corrupted")
    return None


def blob_sweep(session: Any) -> None:
    """Delete the chunk sets whose owner row is gone or no longer points at them.

    Owner rows are deleted in bulk or by cascade, which leaves their chunks behind. Call before the
    commit of every path that deletes ``bw_plugins``, ``bw_plugin_pages`` or ``bw_jobs_cache`` rows."""
    # Pending owner rows must be visible to the live-marker reads below.
    session.flush()
    # The sets are read once, before the live markers: a set another transaction commits after this
    # read is never a deletion candidate, whatever the markers say.
    sets = session.execute(select(Blob_chunks.owner, Blob_chunks.checksum).distinct()).all()
    if not sets:
        return
    owners = {owner for owner, _ in sets}
    live = set()
    for table, key, column, as_int in (
        ("bw_plugins", Plugins.id, Plugins.data, False),
        ("bw_plugin_pages", Plugin_pages.plugin_id, Plugin_pages.data, False),
        ("bw_jobs_cache", Jobs_cache.id, Jobs_cache.data, True),
    ):
        ids = [owner.split(":", 1)[1] for owner in owners if owner.startswith(f"{table}:")]
        if as_int:
            ids = [int(i) for i in ids if i.isdigit()]
        for start in range(0, len(ids), _SWEEP_BATCH):
            for row_key, value in session.execute(
                select(key, column).where(key.in_(ids[start : start + _SWEEP_BATCH]), func.length(column) == BLOB_MARKER_LENGTH)
            ):
                checksum = _blob_reference(value)
                if checksum is not None:
                    live.add((f"{table}:{row_key}", checksum))
    for owner, checksum in sets:
        if (owner, checksum) not in live:
            blob_drop(session, Blob_chunks.owner == owner, Blob_chunks.checksum == checksum)
