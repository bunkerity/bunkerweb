"""A refused service save must not be flashed as a success.

`update_service` decided the final flash's *type* by string-matching `operation` against
("Can't", "The database is read-only") instead of the `error` flag it already holds
(services.py, `update_service`). Two real consequences: a backend refusal whose message matches
neither prefix (e.g. `IGNORE_REGEX_CHECK=yes` turns a genuine refusal into an
`ApiUnavailableError` string via the 500 `PUT /global_settings/config` answers with) was flashed
green; and a save where the UI's own regex gate refused at least one field -- reverting it to its
stored value, or dropping it outright when it is not editable -- still ended on an unconditional
green "successfully saved", next to the red flash(es) the operator has to notice on their own.

`update_service` now passes `check_variables` a `refused` list it owns, and `check_variables`
appends one message per refusal to it (`models/config.py:report_error`), whatever the refusal
shape -- reverted or dropped. That count decides the final flash. A fresh, caller-owned list is
used rather than diffing `DATA["TO_FLASH"]` around the call: `check_variables`'s own first line is
`self.__data.load_from_file()`, which *replaces* that queue with whatever is on disk -- a length
taken before the call and one taken after can belong to two different list objects. A value
compare (posted vs. returned) has a false positive of its own besides: `check_variables`
canonicalizes a *valid* value (trim, list rejoin, case), so a legitimate no-op edit can come back
equal to what is stored with nothing actually refused. Covered below.

Same harness as `test_custom_config_save_advisory.py`: load the real `services.py` with its
collaborators mocked, drive the real `update_service`, and read back what it queued in
`DATA["TO_FLASH"]`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]


def _import_services_module():
    """Same loader as `test_custom_config_save_advisory.py`, under its own module name so the two
    loads never share a Blueprint object."""
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.CORE_PLUGINS_PATH = REPO_ROOT / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._services_test_save_flash_type"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_services_module()


class _FakeData(dict):
    def load_from_file(self):
        pass


def _save(monkeypatch, *, edit_service_return, stored=None, posted_extra=None, check_variables_side_effect=None):
    """Drive the real `update_service` for an existing service and return what was flashed."""
    api = Mock()
    api.get_service.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}, **(stored or {})}
    api.get_configs.return_value = []
    api.get_templates.return_value = {}

    bw_config = Mock()
    bw_config.check_variables.side_effect = check_variables_side_effect or (lambda variables, *args, **kwargs: variables)
    bw_config.edit_service.return_value = edit_service_return

    data = _FakeData(TO_FLASH=[])
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", data)
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)

    posted = {"SERVER_NAME": "app.example.com", "USE_UI": "no"} | (posted_extra or {})
    MODULE.update_service("app.example.com", posted, False, "easy", "", {})

    assert bw_config.edit_service.called, "edit_service was never reached -- this test proves nothing"
    return list(data["TO_FLASH"])


def test_a_backend_refusal_matching_neither_prefix_is_flashed_error(monkeypatch):
    """IGNORE_REGEX_CHECK=yes: `PUT /global_settings/config` maps a client-side refusal to a
    500, `base_api_client` surfaces it as `ApiUnavailableError(...)`, and `str(e)` starts with
    neither "Can't" nor "The database is read-only" -- the exact miss the prefix match had."""
    flashed = _save(monkeypatch, edit_service_return=("ApiUnavailableError: API returned 500", 1))

    assert any(f["type"] == "error" and f["content"] == "ApiUnavailableError: API returned 500" for f in flashed), flashed
    assert not any(f["type"] == "success" for f in flashed), flashed


def test_a_value_the_regex_gate_reverted_ends_on_a_warning_not_a_success(monkeypatch):
    def revert_test_setting(variables, config, to_check, *, refused=None, **kwargs):
        # Mirrors `models/config.py:check_variables` on an existing service: `report_error`
        # appends the refusal to the caller's `refused` list and `reject_value` restores the
        # field to what is already stored instead of dropping it.
        if refused is not None:
            refused.append("Variable TEST_SETTING is not valid.")
        variables = dict(variables)
        variables["TEST_SETTING"] = config["TEST_SETTING"]["value"]
        return variables

    flashed = _save(
        monkeypatch,
        edit_service_return=("Configuration for app.example.com has been edited.", 0),
        stored={"TEST_SETTING": {"value": "old-value", "method": "ui"}},
        posted_extra={"TEST_SETTING": "not-a-valid-value"},
        check_variables_side_effect=revert_test_setting,
    )

    assert not any(f["type"] == "success" and "saved for service" in f["content"] for f in flashed), flashed
    assert any(f["type"] == "warning" and "refused" in f["content"] for f in flashed), flashed


def test_a_value_dropped_as_not_editable_also_ends_on_a_warning(monkeypatch):
    """The other refusal shape: `check_variables` pops a blacklisted/unknown/foreign-method key
    instead of reverting it (`variables.pop(key, None)`, `models/config.py:254/262/268/279`) --
    still a refusal that a value comparison alone would miss, since the key is simply gone."""

    def drop_test_setting(variables, config, to_check, *, refused=None, **kwargs):
        if refused is not None:
            refused.append("Variable TEST_SETTING is not editable, ignoring it.")
        variables = dict(variables)
        variables.pop("TEST_SETTING", None)
        return variables

    flashed = _save(
        monkeypatch,
        edit_service_return=("Configuration for app.example.com has been edited.", 0),
        posted_extra={"TEST_SETTING": "whatever"},
        check_variables_side_effect=drop_test_setting,
    )

    assert not any(f["type"] == "success" and "saved for service" in f["content"] for f in flashed), flashed
    assert any(f["type"] == "warning" and "refused" in f["content"] for f in flashed), flashed


def test_a_value_only_canonicalized_by_the_gate_is_not_mistaken_for_a_refusal(monkeypatch):
    """A *valid* value that `check_variables` merely canonicalizes (trim / list-rejoin / case)
    can come back out of it equal to the stored value with nothing refused at all -- the false
    positive a before/after value comparison would produce, and the reason the fix counts what
    `check_variables` itself reports through `refused` instead."""

    def canonicalize_test_setting(variables, config, to_check, *, refused=None, **kwargs):
        # Nothing appended to `refused`: check_variables never reports a problem for a valid value.
        variables = dict(variables)
        variables["TEST_SETTING"] = config["TEST_SETTING"]["value"]
        return variables

    flashed = _save(
        monkeypatch,
        edit_service_return=("Configuration for app.example.com has been edited.", 0),
        stored={"TEST_SETTING": {"value": "10.0.0.1 10.0.0.2", "method": "ui"}},
        posted_extra={"TEST_SETTING": "10.0.0.1  10.0.0.2"},
        check_variables_side_effect=canonicalize_test_setting,
    )

    assert any(f["type"] == "success" and "saved for service" in f["content"] for f in flashed), flashed
    assert not any(f["type"] == "warning" for f in flashed), flashed


def test_a_clean_save_is_still_flashed_success(monkeypatch):
    flashed = _save(monkeypatch, edit_service_return=("Configuration for app.example.com has been edited.", 0))

    assert any(f["type"] == "success" and "saved for service" in f["content"] for f in flashed), flashed
    assert not any(f["type"] == "warning" for f in flashed), flashed


def test_the_read_only_refusal_is_still_flashed_error(monkeypatch):
    flashed = _save(monkeypatch, edit_service_return=("The database is read-only, the changes will not be saved", 1))

    assert any(f["type"] == "error" and "read-only" in f["content"] for f in flashed), flashed
    assert not any(f["type"] == "success" for f in flashed), flashed


def test_a_prior_flash_in_the_same_request_never_pollutes_the_refusal_count(monkeypatch):
    """Round-2 Criticos regression, closed by construction rather than by timing. The old attempt
    inferred the refusal count from `len(DATA["TO_FLASH"])` before/after the `check_variables`
    call -- but `check_variables`'s own first line is `self.__data.load_from_file()`
    (`models/config.py:183`), which *replaces* `DATA["TO_FLASH"]` with whatever is on disk,
    discarding an in-memory-only flash appended earlier in the same request (e.g.
    `services.py:1235`'s non-editable-template-config warning, since `.append()` never persists)
    -- so a before/after length diff could net out wrong in either direction. Passing
    `check_variables` a fresh, caller-owned `refused` list sidesteps `DATA["TO_FLASH"]` (and its
    reload) entirely: an earlier flash already sitting in the queue must not change what this
    call reports."""

    def refuse_one_value(variables, config, to_check, *, refused=None, **kwargs):
        assert refused == [], "the list handed to check_variables must start empty for this call"
        if refused is not None:
            refused.append("Variable TEST_SETTING is not valid.")
        return dict(variables)

    api = Mock()
    api.get_service.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}}
    api.get_configs.return_value = []
    api.get_templates.return_value = {}

    bw_config = Mock()
    bw_config.check_variables.side_effect = refuse_one_value
    bw_config.edit_service.return_value = ("Configuration for app.example.com has been edited.", 0)

    data = _FakeData(TO_FLASH=[])
    # A flash from earlier in this same request, already queued before check_variables runs.
    data["TO_FLASH"].append({"content": "Custom config X is not editable.", "type": "error"})

    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", data)
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)

    posted = {"SERVER_NAME": "app.example.com", "USE_UI": "no", "TEST_SETTING": "irrelevant"}
    MODULE.update_service("app.example.com", posted, False, "easy", "", {})

    assert bw_config.edit_service.called, "edit_service was never reached -- this test proves nothing"
    flashed = list(data["TO_FLASH"])
    assert not any(f["type"] == "success" and "saved for service" in f["content"] for f in flashed), flashed
    # Exactly one refusal was reported for THIS call -- "1 value(s)", not 2 (the prior flash) or 0.
    # Exact wording pinned: "successfully" dropped and joined with ", but" once a value was refused.
    assert any(
        f["type"] == "warning" and f["content"] == "Configuration saved for service app.example.com, but 1 value(s) were refused." for f in flashed
    ), flashed
