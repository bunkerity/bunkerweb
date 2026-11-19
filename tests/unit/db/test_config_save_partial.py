"""A partial save decides each posted key as a save that carried every stored global row did.

``partial=True`` sends only the keys a caller changes. The active global template and the sibling members of a
multiple setting still decide what a posted key means, and a row that is not posted is neither deleted nor re-owned.
Each scenario runs once with the stored rows in the payload (the reference, what a full snapshot does) and once partially.
"""

import sqlite3
from contextlib import contextmanager

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from fixtures.seed import add_global_value, make_core_plugin, make_general_settings, session
from Database import Database
from model import Global_values, Metadata, Plugins, Template_settings

PARTIAL, FULL = "partial", "full"


def _setting(default, *, multiple=None):
    return {"id": "x", "context": "multisite", "default": default, "help": "h", "label": "L", "regex": "^.*$", "type": "text", "multiple": multiple}


@pytest.fixture
def seeded(db):
    plugin = make_core_plugin(
        "proxy",
        settings={
            "USE_REVERSE_PROXY": _setting("no"),
            "REVERSE_PROXY_URL": _setting("/", multiple="reverse-proxy"),
            "REVERSE_PROXY_HOST": _setting("", multiple="reverse-proxy"),
            "USE_TEMPLATE": _setting(""),
            "OTHER": _setting("def"),
            "FILE_X": {**_setting(""), "type": "file"},
        },
    )
    for key, setting in plugin["settings"].items():
        setting["id"] = key.lower().replace("_", "-")
        if setting["multiple"] is None:
            del setting["multiple"]
    db.init_tables([make_general_settings(), plugin])
    db.initialize_db("1.7.0", "Docker")
    template = {
        "name": "Proxy",
        "settings": {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_URL_1": "/api", "REVERSE_PROXY_HOST_1": "http://tpl"},
        "steps": [{"title": "Proxy", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1", "REVERSE_PROXY_HOST_1"], "configs": []}],
    }
    assert db.create_template("proxy", **template) == ""
    return db


def _rows(db):
    with session(db) as s:
        return {(r.setting_id, r.suffix): (r.value, r.method) for r in s.scalars(select(Global_values))}


def _save(db, mode, posted):
    if mode == PARTIAL:
        return db.save_config(posted, "api", skip_service_management=True, partial=True)
    stored = {(f"{k}_{n}" if n else k): v for (k, n), (v, _) in _rows(db).items()}
    return db.save_config({**stored, **posted}, "api", skip_service_management=True)


@pytest.mark.parametrize("mode", (FULL, PARTIAL))
def test_a_value_equal_to_the_default_overrides_the_active_template(seeded, mode):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")

    assert isinstance(_save(seeded, mode, {"USE_REVERSE_PROXY": "no"}), set)

    assert _rows(seeded)[("USE_REVERSE_PROXY", 0)] == ("no", "api")
    assert _rows(seeded)[("USE_TEMPLATE", 0)] == ("proxy", "ui")
    assert seeded.get_config(global_only=True)["USE_REVERSE_PROXY"] == "no"


@pytest.mark.parametrize("mode", (FULL, PARTIAL))
def test_resetting_one_member_of_a_slot_keeps_the_same_rows_as_a_full_save(seeded, mode):
    add_global_value(seeded, setting_id="REVERSE_PROXY_URL", value="/app", method="ui", suffix=1)
    add_global_value(seeded, setting_id="REVERSE_PROXY_HOST", value="http://h", method="ui", suffix=1)
    add_global_value(seeded, setting_id="OTHER", value="kept", method="wizard")

    assert isinstance(_save(seeded, mode, {"REVERSE_PROXY_URL_1": "/"}), set)

    rows = _rows(seeded)
    assert ("REVERSE_PROXY_URL", 1) not in rows
    assert rows[("REVERSE_PROXY_HOST", 1)] == ("http://h", "ui")
    assert rows[("OTHER", 0)] == ("kept", "wizard")
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    assert seeded.get_config(global_only=True)["REVERSE_PROXY_URL_1"] == "/api"


@pytest.mark.parametrize("owner", ("ui", "api", "wizard", "scheduler", "autoconf"))
def test_a_row_that_is_not_posted_keeps_its_value_and_owner(seeded, owner):
    add_global_value(seeded, setting_id="OTHER", value="kept", method=owner)

    assert isinstance(_save(seeded, PARTIAL, {"USE_REVERSE_PROXY": "yes"}), set)

    assert _rows(seeded)[("OTHER", 0)] == ("kept", owner)


def test_a_draft_row_is_not_read_as_context(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    with session(seeded) as s:
        s.scalars(select(Global_values).filter_by(setting_id="USE_TEMPLATE")).one().is_draft = True

    assert isinstance(_save(seeded, PARTIAL, {"USE_REVERSE_PROXY": "no"}), set)

    assert ("USE_REVERSE_PROXY", 0) not in _rows(seeded)


def test_without_partial_a_save_still_clears_a_row_it_does_not_post(seeded):
    add_global_value(seeded, setting_id="OTHER", value="stale", method="ui")

    assert isinstance(seeded.save_config({"USE_REVERSE_PROXY": "yes"}, "api", skip_service_management=True), set)

    assert ("OTHER", 0) not in _rows(seeded)


def _flags(db):
    """Every change flag a save can raise, plus the rows, so a no-op save can be compared byte for byte."""
    with session(db) as s:
        meta = s.get(Metadata, 1)
        return {
            "custom_configs_changed": meta.custom_configs_changed,
            "first_config_saved": meta.first_config_saved,
            "plugins": {p.id for p in s.scalars(select(Plugins)) if p.config_changed},
            "rows": _rows(db),
        }


def _clear_flags(db):
    with session(db) as s:
        s.get(Metadata, 1).custom_configs_changed = False
        s.query(Plugins).update({Plugins.config_changed: False})


def test_an_empty_partial_save_with_an_active_template_changes_nothing(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    add_global_value(seeded, setting_id="OTHER", value="kept", method="ui")
    _clear_flags(seeded)
    before = _flags(seeded)

    assert seeded.save_config({}, "api", skip_service_management=True, partial=True) == set()

    assert _flags(seeded) == before


@pytest.mark.parametrize("mode", (FULL, PARTIAL))
def test_a_posted_key_under_an_active_template_flags_the_template_change(seeded, mode):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="api")
    _clear_flags(seeded)

    assert isinstance(_save(seeded, mode, {"OTHER": "x"}), set)

    flags = _flags(seeded)
    assert flags["custom_configs_changed"] is True
    assert flags["plugins"] == {"proxy"}


def test_a_stored_row_that_is_not_posted_does_not_raise_the_template_flag(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="api")
    add_global_value(seeded, setting_id="OTHER", value="kept", method="ui")
    _clear_flags(seeded)

    # only keys the save did not touch exist besides the posted one, which equals its stored value
    assert isinstance(seeded.save_config({"OTHER": "kept"}, "api", skip_service_management=True, partial=True), set)

    assert _flags(seeded)["plugins"] == set()
    assert _rows(seeded)[("OTHER", 0)] == ("kept", "ui")


def test_the_same_partial_save_twice_leaves_every_change_flag_as_it_was(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")

    assert isinstance(_save(seeded, PARTIAL, {"OTHER": "x"}), set)
    assert _flags(seeded)["custom_configs_changed"] is True  # the first PATCH persisted a row
    _clear_flags(seeded)
    before = _flags(seeded)

    assert _save(seeded, PARTIAL, {"OTHER": "x"}) == set()

    assert _flags(seeded) == before


@pytest.mark.parametrize("posted", ({"OTHER": "y"}, {"OTHER": "def"}), ids=("update", "delete"))
def test_a_posted_key_that_changes_or_removes_a_stored_row_flags_the_template_change(seeded, posted):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    add_global_value(seeded, setting_id="OTHER", value="x", method="api")
    _clear_flags(seeded)

    assert isinstance(_save(seeded, PARTIAL, posted), set)

    flags = _flags(seeded)
    assert flags["custom_configs_changed"] is True
    assert flags["plugins"] == {"proxy"}


def _commit_after_layering(monkeypatch, change):
    """Run ``change`` on a second connection right after the stored rows were read as context."""
    original = Database._layer_over_stored_global_values
    fired = []

    def layered(session_, config):
        merged = original(session_, config)
        if not fired:  # a save run by ``change`` reads its own context: hook the first one only
            fired.append(True)
            change()
        return merged

    monkeypatch.setattr(Database, "_layer_over_stored_global_values", staticmethod(layered))


def test_a_stored_row_updated_after_the_context_read_keeps_its_new_value_and_owner(seeded, monkeypatch):
    add_global_value(seeded, setting_id="OTHER", value="old", method="ui")

    def update():
        with session(seeded) as s:
            row = s.scalars(select(Global_values).filter_by(setting_id="OTHER")).one()
            row.value, row.method = "new", "ui"

    _commit_after_layering(monkeypatch, update)

    assert isinstance(_save(seeded, PARTIAL, {"USE_REVERSE_PROXY": "yes"}), set)

    assert _rows(seeded)[("OTHER", 0)] == ("new", "ui")
    assert _rows(seeded)[("USE_REVERSE_PROXY", 0)] == ("yes", "api")


def test_a_stored_row_deleted_after_the_context_read_stays_deleted(seeded, monkeypatch):
    add_global_value(seeded, setting_id="OTHER", value="old", method="ui")

    def delete():
        with session(seeded) as s:
            s.query(Global_values).filter_by(setting_id="OTHER").delete()

    _commit_after_layering(monkeypatch, delete)

    assert isinstance(_save(seeded, PARTIAL, {"USE_REVERSE_PROXY": "yes"}), set)

    assert ("OTHER", 0) not in _rows(seeded)
    assert _rows(seeded)[("USE_REVERSE_PROXY", 0)] == ("yes", "api")


def _reset_sibling_inside_the_window(seeded, monkeypatch, key, value):
    """Another PATCH resets ``key`` on its own connection right after this save read its context."""
    _commit_after_layering(monkeypatch, lambda: _save(seeded, PARTIAL, {key: value}))


def _add_file_row(db, method):
    add_global_value(db, setting_id="FILE_X", value="a", method=method)
    with session(db) as s:
        s.scalars(select(Global_values).filter_by(setting_id="FILE_X")).one().file_name = "x.conf"


def _seed_slot(seeded, owner="ui"):
    add_global_value(seeded, setting_id="REVERSE_PROXY_URL", value="/app", method=owner, suffix=1)
    add_global_value(seeded, setting_id="REVERSE_PROXY_HOST", value="http://h", method=owner, suffix=1)


@pytest.mark.parametrize("first", ("url", "host"))
def test_two_resets_of_one_slot_keep_one_member_whatever_the_interleaving(seeded, monkeypatch, first):
    """The sibling that anchors the slot may be reset by another PATCH after the context read: the slot must survive."""
    _seed_slot(seeded)
    url, host = ("REVERSE_PROXY_URL_1", "/"), ("REVERSE_PROXY_HOST_1", "")
    outer, inner = (url, host) if first == "url" else (host, url)
    _reset_sibling_inside_the_window(seeded, monkeypatch, *inner)

    assert isinstance(_save(seeded, PARTIAL, dict([outer])), set)

    slot = {key: row for key, row in _rows(seeded).items() if key[0].startswith("REVERSE_PROXY")}
    assert len(slot) == 1, slot  # both serial orders keep exactly one default-valued row, never none


@pytest.mark.parametrize("serial", ("url then host", "host then url"))
def test_two_serial_resets_of_one_slot_keep_one_member(seeded, serial):
    _seed_slot(seeded)
    steps = [("REVERSE_PROXY_URL_1", "/"), ("REVERSE_PROXY_HOST_1", "")]
    for key, value in steps if serial == "url then host" else steps[::-1]:
        assert isinstance(_save(seeded, PARTIAL, {key: value}), set)

    assert len({key for key in _rows(seeded) if key[0].startswith("REVERSE_PROXY")}) == 1


def test_a_sibling_that_still_anchors_the_slot_after_the_context_read_lets_the_reset_delete_its_row(seeded, monkeypatch):
    _seed_slot(seeded)

    def move_sibling():
        with session(seeded) as s:
            s.scalars(select(Global_values).filter_by(setting_id="REVERSE_PROXY_HOST")).one().value = "http://moved"

    _commit_after_layering(monkeypatch, move_sibling)

    assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)

    rows = _rows(seeded)
    assert ("REVERSE_PROXY_URL", 1) not in rows
    assert rows[("REVERSE_PROXY_HOST", 1)] == ("http://moved", "ui")


def test_the_slot_rows_are_write_locked_before_the_sibling_is_trusted(seeded, monkeypatch):
    """On sqlite another connection cannot write between the sibling check and the commit; other engines lock the rows."""
    if seeded.sql_engine.dialect.name != "sqlite":
        pytest.skip("write lock probed through a second sqlite connection")
    _seed_slot(seeded)
    errors = []
    original = Database._read_global_rows_locked

    def probe(self_, session_, rows):
        found = original(self_, session_, rows)
        other = sqlite3.connect(seeded.sql_engine.url.database, timeout=0)
        try:
            other.execute("UPDATE bw_global_values SET value = value")
        except sqlite3.OperationalError as e:
            errors.append(str(e))
        finally:
            other.close()
        return found

    monkeypatch.setattr(Database, "_read_global_rows_locked", probe)

    assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)

    assert errors == ["database is locked"]


def test_a_refused_partial_save_over_a_scheduler_row_with_a_file_name_raises_no_signal(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    _add_file_row(seeded, "scheduler")
    _clear_flags(seeded)
    with session(seeded) as s:
        s.get(Metadata, 1).first_config_saved = True  # any non-empty save sets it once: only the template signal is under test
    before = _flags(seeded)

    assert isinstance(_save(seeded, PARTIAL, {"FILE_X": "b"}), set)

    assert _flags(seeded) == before
    with session(seeded) as s:
        row = s.scalars(select(Global_values).filter_by(setting_id="FILE_X")).one()
        assert (row.value, row.method, row.file_name, row.is_draft) == ("a", "scheduler", "x.conf", False)


def test_a_permitted_file_name_change_still_raises_the_signal(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    _add_file_row(seeded, "api")
    _clear_flags(seeded)

    assert isinstance(seeded.save_config({"FILE_X": "a"}, "api", skip_service_management=True, partial=True, file_names={"FILE_X": "y.conf"}), set)

    assert _flags(seeded)["custom_configs_changed"] is True


def _write_order(db, action):
    """Run ``action`` and return which of the plugin rows and the global rows it touched first (a write or a locking read)."""
    seen = []

    def record(conn, cursor, statement, parameters, context, executemany):
        text = statement.lstrip().upper()
        if text.startswith("UPDATE BW_PLUGINS"):
            seen.append("plugins")
        elif "BW_GLOBAL_VALUES" in text.split("WHERE")[0] and text.startswith(("UPDATE", "DELETE", "INSERT")) or "FOR UPDATE" in text:
            seen.append("globals")

    event.listen(db.sql_engine, "before_cursor_execute", record)
    try:
        action()
    finally:
        event.remove(db.sql_engine, "before_cursor_execute", record)
    return seen[: seen.index("globals") + 1] if "globals" in seen else seen


def test_the_guarded_partial_save_and_a_full_save_touch_the_plugin_rows_before_the_global_rows(seeded):
    _seed_slot(seeded)
    guarded = _write_order(seeded, lambda: _save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}))
    with session(seeded) as s:
        s.query(Global_values).filter(Global_values.setting_id.like("REVERSE_PROXY%")).delete(synchronize_session=False)
    _seed_slot(seeded)  # put the slot back for the full save
    full = _write_order(seeded, lambda: _save(seeded, FULL, {"REVERSE_PROXY_URL_1": "/"}))

    assert guarded == full == ["plugins", "globals"]


def test_a_sibling_skipped_as_a_draft_does_not_anchor_the_slot(seeded):
    add_global_value(seeded, setting_id="REVERSE_PROXY_URL", value="/app", method="ui", suffix=1)
    add_global_value(seeded, setting_id="REVERSE_PROXY_HOST", value="http://h", method="ui", suffix=1)
    with session(seeded) as s:
        s.scalars(select(Global_values).filter_by(setting_id="REVERSE_PROXY_HOST")).one().is_draft = True

    assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/", "REVERSE_PROXY_HOST_1": "http://x"}), set)

    with session(seeded) as s:
        rows = {r.setting_id: (r.value, r.is_draft) for r in s.scalars(select(Global_values))}
    assert rows["REVERSE_PROXY_URL"] == ("/", False)  # the last active member stays, the draft is no anchor
    assert rows["REVERSE_PROXY_HOST"] == ("http://h", True)


def test_a_refused_reset_takes_no_write_lock(seeded):
    """A reset the caller may not make changes nothing, so it must not hold the database-wide sqlite write lock."""
    if seeded.sql_engine.dialect.name != "sqlite":
        pytest.skip("write lock probed through a second sqlite connection")
    _seed_slot(seeded, owner="scheduler")
    with session(seeded) as s:
        s.get(Metadata, 1).first_config_saved = True  # no other write: the save's own bookkeeping stays out of the probe
    errors = []

    def probe(_):
        other = sqlite3.connect(seeded.sql_engine.url.database, timeout=0)
        try:
            other.execute("UPDATE bw_global_values SET value = value")
            other.commit()
        except sqlite3.OperationalError as e:
            errors.append(str(e))
        finally:
            other.close()

    event.listen(seeded.sql_engine, "commit", probe)
    try:
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)
    finally:
        event.remove(seeded.sql_engine, "commit", probe)

    assert errors == []
    assert _rows(seeded)[("REVERSE_PROXY_URL", 1)] == ("/app", "scheduler")


def test_a_lock_conflict_on_the_slot_recomputes_the_save_once(seeded, monkeypatch):
    """MariaDB's snapshot isolation fails the locking read (1020) when a sibling changed: the save reads again and succeeds."""
    _seed_slot(seeded)
    original = Database._read_global_rows_locked
    calls = []

    def conflicting(self_, session_, rows):
        calls.append(rows)
        if len(calls) == 1:
            raise OperationalError("SELECT ... FOR UPDATE", {}, Exception("(1020, 'Record has changed since last read')"))
        return original(self_, session_, rows)

    monkeypatch.setattr(Database, "_read_global_rows_locked", conflicting)

    assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)

    assert len(calls) == 2
    rows = _rows(seeded)
    assert ("REVERSE_PROXY_URL", 1) not in rows
    assert rows[("REVERSE_PROXY_HOST", 1)] == ("http://h", "ui")


def test_a_lock_conflict_that_repeats_returns_the_error_and_keeps_every_row(seeded, monkeypatch):
    _seed_slot(seeded)

    def conflicting(self_, session_, rows):
        raise OperationalError("SELECT ... FOR UPDATE", {}, Exception("deadlock"))

    monkeypatch.setattr(Database, "_read_global_rows_locked", conflicting)

    assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), str)

    assert _rows(seeded)[("REVERSE_PROXY_URL", 1)] == ("/app", "ui")


@contextmanager
def _commit_before_the_first_write(db, change):
    """Run ``change`` on a second connection after the save decided (per-key loop) and before it writes or locks anything."""
    fired = []

    def hook(conn, cursor, statement, parameters, context, executemany):
        text = statement.lstrip().upper()
        if not fired and (text.startswith(("UPDATE", "DELETE", "INSERT")) or "FOR UPDATE" in text):
            fired.append(True)  # ``change`` runs statements of its own
            change()

    event.listen(db.sql_engine, "before_cursor_execute", hook)
    try:
        yield
    finally:
        event.remove(db.sql_engine, "before_cursor_execute", hook)
    assert fired, "the save never reached a write"


def test_a_no_op_sibling_deleted_before_the_lock_does_not_anchor_the_slot(seeded):
    """The posted sibling equals its stored value, so the save queues nothing for it: its locked row is the input, not the payload."""
    _seed_slot(seeded)

    def delete_sibling():
        with session(seeded) as s:
            s.query(Global_values).filter_by(setting_id="REVERSE_PROXY_HOST").delete()

    with _commit_before_the_first_write(seeded, delete_sibling):
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/", "REVERSE_PROXY_HOST_1": "http://h"}), set)

    slot = {key for key in _rows(seeded) if key[0].startswith("REVERSE_PROXY")}
    assert len(slot) == 1, slot  # the slot never ends up empty


def test_a_target_row_taken_by_the_scheduler_before_the_lock_is_not_reset(seeded):
    _seed_slot(seeded)

    def scheduler_takes_the_row():
        with session(seeded) as s:
            s.scalars(select(Global_values).filter_by(setting_id="REVERSE_PROXY_URL")).one().method = "scheduler"

    with _commit_before_the_first_write(seeded, scheduler_takes_the_row):
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)

    assert _rows(seeded)[("REVERSE_PROXY_URL", 1)] == ("/app", "scheduler")
    assert _rows(seeded)[("REVERSE_PROXY_HOST", 1)] == ("http://h", "ui")


def test_a_posted_sibling_taken_by_the_scheduler_with_the_same_value_is_not_overwritten(seeded):
    """The sibling's value is unchanged, but its owner is an input of the decision: the queued API update must not take the row."""
    _seed_slot(seeded)

    def scheduler_takes_the_sibling():
        with session(seeded) as s:
            s.scalars(select(Global_values).filter_by(setting_id="REVERSE_PROXY_HOST")).one().method = "scheduler"

    with _commit_before_the_first_write(seeded, scheduler_takes_the_sibling):
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/", "REVERSE_PROXY_HOST_1": "http://new"}), set)

    rows = _rows(seeded)
    assert rows[("REVERSE_PROXY_HOST", 1)] == ("http://h", "scheduler")
    assert ("REVERSE_PROXY_URL", 1) not in rows  # the scheduler's row still anchors the slot


def test_a_template_activated_before_the_lock_does_not_let_the_save_delete_the_explicit_value(seeded):
    """Under the new template ``/`` is no longer the default: the explicit row must stay, as in a save run after the activation."""
    _seed_slot(seeded)

    def activate_template():
        add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")

    with _commit_before_the_first_write(seeded, activate_template):
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)

    assert _rows(seeded)[("REVERSE_PROXY_URL", 1)] == ("/", "api")


def test_a_template_default_edited_before_the_lock_does_not_let_the_save_delete_the_explicit_value(seeded):
    add_global_value(seeded, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    _seed_slot(seeded)

    def edit_template_default():
        with session(seeded) as s:
            s.scalars(select(Template_settings).filter_by(template_id="proxy", setting_id="REVERSE_PROXY_URL", suffix=1)).one().default = "/edited"

    with _commit_before_the_first_write(seeded, edit_template_default):
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/api"}), set)

    assert _rows(seeded)[("REVERSE_PROXY_URL", 1)] == ("/api", "api")


def test_a_plain_row_taken_by_the_scheduler_before_the_lock_is_not_deleted(seeded):
    add_global_value(seeded, setting_id="OTHER", value="old", method="ui")

    def scheduler_takes_the_row():
        with session(seeded) as s:
            s.scalars(select(Global_values).filter_by(setting_id="OTHER")).one().method = "scheduler"

    with _commit_before_the_first_write(seeded, scheduler_takes_the_row):
        assert isinstance(_save(seeded, PARTIAL, {"OTHER": "def"}), set)

    assert _rows(seeded)[("OTHER", 0)] == ("old", "scheduler")


def test_a_default_member_skipped_next_to_an_anchor_is_inserted_when_the_anchor_goes_before_the_lock(seeded):
    add_global_value(seeded, setting_id="REVERSE_PROXY_HOST", value="http://h", method="ui", suffix=1)

    def delete_anchor():
        with session(seeded) as s:
            s.query(Global_values).filter_by(setting_id="REVERSE_PROXY_HOST").delete()

    with _commit_before_the_first_write(seeded, delete_anchor):
        assert isinstance(_save(seeded, PARTIAL, {"REVERSE_PROXY_URL_1": "/"}), set)

    assert _rows(seeded)[("REVERSE_PROXY_URL", 1)] == ("/", "api")  # the slot is not left empty
