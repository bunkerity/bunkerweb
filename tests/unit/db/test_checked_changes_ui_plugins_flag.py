"""``checked_changes`` must not clear the Web UI plugin reload flag on a default-list acknowledgement.

``reload_ui_plugins`` belongs to the Web UI: it clears it itself with an explicit ``["ui_plugins"]``.
A caller that acknowledges "everything" with no list and ``value=False`` (``POST /system/checked_changes``
reaches that) used to clear it too, so a restart lost the order to re-extract the updated plugin pages.
Setting (``value=True``, a restore or an import) still raises it with the default list.
"""

from fixtures.seed import seed_minimal


def _flag(db):
    return db.get_metadata()["reload_ui_plugins"]


def test_default_list_acknowledgement_keeps_the_flag(db):
    seed_minimal(db)
    assert db.checked_changes(["ui_plugins"], value=True) == ""
    assert _flag(db) is True

    assert db.checked_changes(value=False) == ""

    assert _flag(db) is True


def test_default_list_setting_raises_the_flag(db):
    seed_minimal(db)
    assert _flag(db) is False

    assert db.checked_changes(value=True) == ""

    assert _flag(db) is True


def test_the_web_ui_clears_it_with_an_explicit_list(db):
    seed_minimal(db)
    assert db.checked_changes(["ui_plugins"], value=True) == ""

    assert db.checked_changes(["ui_plugins"], value=False) == ""

    assert _flag(db) is False


def test_default_list_acknowledgement_still_clears_the_other_flags(db):
    seed_minimal(db)
    assert db.checked_changes(["custom_configs", "external_plugins", "pro_plugins", "instances", "certificates"], value=True) == ""

    assert db.checked_changes(value=False) == ""

    metadata = db.get_metadata()
    assert not any(
        metadata[key] for key in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "instances_changed", "certificates_changed")
    )
