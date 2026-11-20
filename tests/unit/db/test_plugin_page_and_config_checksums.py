"""Regressions for unchanged plugin pages and empty custom-config checksums."""

from hashlib import sha256

import pytest

from fixtures.seed import seed_minimal


@pytest.mark.parametrize("writer", ["save", "upsert"])
@pytest.mark.parametrize("checksum", [None, "", "absent", "supplied-checksum"])
def test_custom_config_checksum_fallback_on_insert_and_update(db, writer, checksum):
    seed_minimal(db)
    for data in ["# initial", b"# updated"]:
        config = {"type": "http", "name": "checksum", "data": data, "method": "manual"}
        if checksum != "absent":
            config["checksum"] = checksum
        if writer == "save":
            result = db.save_custom_configs([config], "manual")
        else:
            result = db.upsert_custom_config("http", "checksum", config)
        assert result == ""
        stored = db.get_custom_config("http", "checksum")
        expected_data = data.encode() if isinstance(data, str) else data
        expected_checksum = checksum if checksum == "supplied-checksum" else sha256(expected_data).hexdigest()
        assert stored["data"] == expected_data
        assert stored["checksum"] == expected_checksum
