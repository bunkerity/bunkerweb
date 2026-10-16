"""Regressions for unchanged plugin pages and empty custom-config checksums."""

from hashlib import sha256

import pytest

from common_utils import create_plugin_tar_gz
from fixtures.seed import add_plugin_page, make_external_plugin, seed_minimal, session
from model import Plugin_pages


def test_unchanged_pro_page_survives_repeated_sync(db, monkeypatch, tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "actions.py").write_text("# unchanged page\n")
    monkeypatch.setattr(db, "_uep_resolve_plugin_dir", lambda *_: tmp_path)
    assert db.update_external_plugins([make_external_plugin("pageplug")], _type="pro") == ""
    data = create_plugin_tar_gz(ui).getvalue()
    checksum = sha256(data).hexdigest()
    add_plugin_page(db, "pageplug", data=data, checksum=checksum)

    assert db.update_external_plugins([make_external_plugin("pageplug")], _type="pro") == ""
    with session(db) as s:
        page = s.query(Plugin_pages).filter_by(plugin_id="pageplug").first()
        assert page is not None
        assert page.checksum == checksum
        assert page.data == data


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
