"""Reject an unreadable or mismatched archive before clearing any database table."""

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src/common/core/backup"))
import backup  # noqa: E402


@pytest.mark.parametrize("damage", ["wrong-engine", "renamed", "missing-member", "not-zip", "missing", "crc-stored", "crc-deflated"])
def test_refusal_preserves_every_table_and_metadata(db, tmp_path, monkeypatch, damage):
    monkeypatch.setattr(backup, "sep", str(tmp_path))
    assert db.initialize_db("1.6.17", "Linux") == ""
    engine = db.database_uri.split(":")[0].split("+")[0]
    source = ("mariadb" if engine != "mariadb" else "mysql") if damage == "wrong-engine" else engine
    archive = tmp_path / f"backup-{source}-2026-11-05_00-00-00.zip"
    if damage == "renamed":
        archive = tmp_path / "renamed.zip"
    compression = ZIP_DEFLATED if damage == "crc-deflated" else ZIP_STORED
    with ZipFile(archive, "w", compression=compression) as zipf:
        zipf.writestr("other.sql" if damage == "missing-member" else archive.with_suffix(".sql").name, b"SELECT 1;\n" * 200)
    if damage.startswith("crc-"):
        raw = bytearray(archive.read_bytes())
        start = 30 + len(archive.with_suffix(".sql").name)
        for offset in range(start + 8, start + 16):
            raw[offset] ^= 0xFF
        archive.write_bytes(raw)
    elif damage == "not-zip":
        archive.write_bytes(b"not a zip")
    elif damage == "missing":
        archive.unlink()
    tables = set(inspect(db.sql_engine).get_table_names())
    metadata = db.get_metadata()

    with pytest.raises((SystemExit, Exception)) as refused:
        backup.restore_database(archive, db)

    assert set(inspect(db.sql_engine).get_table_names()) == tables
    assert db.get_metadata() == metadata
    assert isinstance(refused.value, SystemExit) and refused.value.code == 1
    with db.sql_engine.connect() as conn:
        assert conn.execute(text("SELECT version FROM bw_metadata WHERE id = 1")).scalar() == "1.6.17"
