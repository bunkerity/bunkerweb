"""A UI service rename saves its custom configs through the ONE bulk path, like every other save.

`routes/services.py` used to take a private per-config `create`/`update` loop whenever the service
was renamed, because `save_config` hard-deleted the renamed service and `ON DELETE CASCADE` took its
`bw_custom_configs` rows with it. The shared layer now renames the row instead
(`db_methods/config_save.py`, `_sc_apply_service_rename`), so that loop bought nothing and cost two
things: `create_config` answered "already exists" for every surviving config, and the `update_config`
fallback then hit the API's "No values were changed" 400 for any config this submission did not
change — flashing an error on a rename that had fully succeeded and `break`ing out of the loop,
silently dropping every remaining entry, including edits made in the same form post.

These tests pin the deletion of that branch: one `PUT /configs/bulk`, nothing per-config, no error
flash, the renamed config re-keyed, and every other service's / other method's config still in the
payload the bulk save replaces its method's rows from.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_save_scope import _import_services_module  # noqa: E402

_services = _import_services_module()

OLD = "old.example.com"
NEW = "new.example.com"


def _config(service, ctype, name, data, method="ui"):
    return {"service": service, "type": ctype, "name": name, "data": data, "method": method, "is_draft": False, "template": None}


@pytest.fixture
def route(monkeypatch):
    """`update_service` with every dependency stubbed, and a real list behind DATA["TO_FLASH"]."""
    flashes = []
    data = {"TO_FLASH": flashes}

    api = Mock()
    api.get_service.return_value = {
        "SERVER_NAME": {"value": OLD, "method": "ui"},
        "IS_DRAFT": {"value": "no", "method": "ui"},
        "USE_TEMPLATE": {"value": "", "method": "ui"},
    }
    api.get_configs.return_value = [
        _config(OLD, "server_http", "mine", "# mine"),
        _config("other.example.com", "server_http", "theirs", "# theirs"),
        _config(None, "http", "globalone", "# global"),
        _config(OLD, "server_http", "fromenv", "# env", method="scheduler"),
    ]
    api.bulk_save_configs.return_value = {}

    bw = Mock()
    bw.check_variables.side_effect = lambda variables, *_args, **_kwargs: variables
    bw.edit_service.return_value = ("Configuration successfully saved.", "")

    monkeypatch.setattr(_services, "API_CLIENT", api)
    monkeypatch.setattr(_services, "BW_CONFIG", bw)
    monkeypatch.setattr(_services, "DATA", data)
    monkeypatch.setattr(_services, "wait_applying", lambda *_a, **_k: None)
    monkeypatch.setattr(_services, "restore_unowned_settings", lambda variables, *_a, **_k: variables)
    monkeypatch.setattr(_services, "get_blacklisted_settings", lambda: set())
    return _services, api, flashes


def _rename(route):
    module, _api, _flashes = route
    module.update_service(
        OLD,
        {"SERVER_NAME": NEW, "OLD_SERVER_NAME": OLD, "USE_REVERSE_PROXY": "yes"},
        False,
        "advanced",
        "",
        {},
    )


def _bulk_payload(api):
    assert api.bulk_save_configs.call_count == 1, "the rename must go through the single bulk path"
    return {(cfg.get("service_id"), cfg["type"], cfg["name"]): cfg for cfg in api.bulk_save_configs.call_args.args[0]}


def test_a_rename_uses_the_bulk_path_and_never_the_per_config_loop(route):
    _module, api, flashes = route

    _rename(route)

    api.create_config.assert_not_called()
    api.update_config.assert_not_called()
    assert [f for f in flashes if f["type"] == "error"] == [], f"a successful rename flashed an error: {flashes}"


def test_the_renamed_services_config_is_re_keyed_in_the_payload(route):
    _module, api, _flashes = route

    _rename(route)

    payload = _bulk_payload(api)
    assert (NEW, "server_http", "mine") in payload
    assert (OLD, "server_http", "mine") not in payload


def test_other_services_and_other_methods_stay_in_the_payload(route):
    """`PUT /configs/bulk` deletes every row of the submitted method and re-inserts from the
    payload (`db_methods/custom_configs.py`), so anything missing from it is a row destroyed.
    A foreign-method row is never deleted by that statement, but it must still be present or the
    bulk save would re-create it under the wrong method."""
    _module, api, _flashes = route

    _rename(route)

    payload = _bulk_payload(api)
    assert ("other.example.com", "server_http", "theirs") in payload
    assert (None, "http", "globalone") in payload
    assert payload[(NEW, "server_http", "fromenv")]["method"] == "scheduler"


def test_a_config_edited_in_the_same_submission_survives_the_rename(route):
    """The failure the deleted `break` caused: an edit posted together with the rename was dropped
    whenever an unchanged config came first in the dict."""
    module, api, _flashes = route

    module.update_service(
        OLD,
        {
            "SERVER_NAME": NEW,
            "OLD_SERVER_NAME": OLD,
            "USE_REVERSE_PROXY": "yes",
            "CUSTOM_CONF_SERVER_HTTP_mine": "# edited in the same post",
        },
        False,
        "easy",
        "",
        {},
    )

    payload = _bulk_payload(api)
    edited = payload[(NEW, "server_http", "mine")]["data"]
    assert b"edited in the same post" in (edited if isinstance(edited, bytes) else edited.encode())


def test_a_refused_rename_never_reaches_the_bulk_save(route):
    """The bulk path is only safe once the rename has actually happened.

    `PUT /configs/bulk` replaces every row of the submitted method from the payload, and that
    payload has already been re-keyed to the NEW name. If `edit_service` refused the rename -- a
    `SERVER_TYPE` switch a still-attached redirect forbids, an inline location the new name would
    collide on, anything `save_config`'s guards turn down -- the database still holds the OLD
    service, so running the bulk save would delete the real rows and re-insert them against a
    service that was never created (invisible forever: `db_methods/custom_configs.py:224` filters
    them out, and SQLite runs with the foreign-keys pragma off, so nothing refuses the write).
    """
    module, api, _flashes = route
    module.BW_CONFIG.edit_service.return_value = ("Cannot switch old.example.com to stream while a redirect is attached", 1)

    _rename(route)

    api.bulk_save_configs.assert_not_called()
    api.create_config.assert_not_called()
    api.update_config.assert_not_called()
    # This submission carried NO config work of its own -- `configs_changed` is True only because
    # the rename re-keyed the payload -- so there is nothing to tell the operator about. Warning
    # here would fire on every refused rename of a service that owns a config.
    assert not any("custom configs were not saved" in flash["content"] for flash in _flashes), _flashes


def test_a_rename_onto_a_name_that_already_exists_does_not_move_the_configs(route):
    """Same gate, the variant that bites on every engine: the new name already belongs to another
    service, so `edit_service` refuses before touching the database (`ui/app/models/config.py`) and
    the target service EXISTS -- the foreign key is satisfied, nothing raises, and the bulk save
    would quietly re-home this service's configs onto somebody else's while the operator reads a
    yellow "already exists." warning saying the rename did not happen."""
    module, api, _flashes = route
    module.BW_CONFIG.edit_service.return_value = (f"Service {NEW} already exists.", 1)

    _rename(route)

    api.bulk_save_configs.assert_not_called()


def test_a_config_edit_dropped_with_a_refused_rename_is_reported(route):
    """The true-positive half: the submission DID carry a config edit, the rename was refused, so the
    edit went with it. The refusal is flashed on its own; nothing else says the config work was
    dropped too, and the operator would otherwise believe their edit landed."""
    module, api, flashes = route
    module.BW_CONFIG.edit_service.return_value = (f"Service {NEW} already exists.", 1)

    module.update_service(
        OLD,
        {
            "SERVER_NAME": NEW,
            "OLD_SERVER_NAME": OLD,
            "USE_REVERSE_PROXY": "yes",
            "CUSTOM_CONF_SERVER_HTTP_mine": "# edited in the same post",
        },
        False,
        "easy",
        "",
        {},
    )

    api.bulk_save_configs.assert_not_called()
    assert any("custom configs were not saved" in flash["content"] for flash in flashes), flashes
    # ...and after the refusal itself, so the operator reads the cause before the consequence.
    contents = [flash["content"] for flash in flashes]
    assert contents.index(f"Service {NEW} already exists.") < next(
        i for i, content in enumerate(contents) if "custom configs were not saved" in content
    ), contents


def test_unchanged_easy_config_on_refused_rename_has_no_dropped_edit_warning(route):
    module, api, flashes = route
    module.BW_CONFIG.edit_service.return_value = (f"Service {NEW} already exists.", 1)
    module.update_service(
        OLD,
        {"SERVER_NAME": NEW, "OLD_SERVER_NAME": OLD, "CUSTOM_CONF_SERVER_HTTP_mine": "# mine"},
        False,
        "easy",
        "",
        {},
    )
    api.bulk_save_configs.assert_not_called()
    assert not any("custom configs were not saved" in flash["content"] for flash in flashes), flashes
