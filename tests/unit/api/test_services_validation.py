"""The services write path must validate before saving.

``POST /services`` and ``PATCH /services/{service}`` used to answer 200 having lost the
value: ``save_config`` runs no regex check of its own, so an unknown key was dropped inside
it and a known key with an illegal value was *written* to ``Services_settings``, echoed back
by ``GET``, and only dropped at generation time by ``Configurator`` with a log line. Same
defect class as ``PATCH /global_settings``.

Follows the module-loader + stubbed-``sys.modules`` pattern of
``test_global_settings_validation.py``: there is no live FastAPI ``TestClient`` in
``tests/unit/api``, so the router function is called directly against a ``Mock`` db.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import schemas  # type: ignore

ROOT = Path(__file__).resolve().parents[3]

SERVICE = "app.example.com"


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    put = get
    patch = get
    # services.py registers a DELETE route; without this the module fails to import.
    delete = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_services": ModuleType("bw_services"),
        "bw_services.routers": ModuleType("bw_services.routers"),
        "bw_services.auth": ModuleType("bw_services.auth"),
        "bw_services.auth.guard": ModuleType("bw_services.auth.guard"),
        "bw_services.schemas": schemas,
        "bw_services.utils": ModuleType("bw_services.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_services"].__path__ = []
    names["bw_services.routers"].__path__ = []
    names["bw_services.auth"].__path__ = []
    names["bw_services.auth.guard"].guard = object()
    names["bw_services.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "services.py"
        spec = importlib.util.spec_from_file_location("bw_services.routers.services", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    # _full_config_snapshot(); the existing roster is what update_service resolves against.
    fake_db.get_non_default_settings.return_value = {"SERVER_NAME": SERVICE}
    fake_db.save_config.return_value = set()
    # A bare Mock() returns a truthy Mock, which the USE_TEMPLATE gate would read as
    # "every layer is unknown" and reject every save. Default it to "all known".
    fake_db.unknown_template_layers.return_value = []
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def _rejecting(*bad_keys):
    """Accept every setting except the named ones."""

    def validate(setting, **_kwargs):
        if setting in bad_keys:
            return False, "not matching regex: '^(no|cookie|captcha)$'"
        return True, ""

    return validate


# --- the value gate ---------------------------------------------------------------


def test_create_rejects_a_value_the_setting_regex_forbids(db):
    db.is_valid_setting.side_effect = _rejecting("USE_ANTIBOT")

    response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={"USE_ANTIBOT": "maybe"}))

    assert response.status_code == 400
    assert "USE_ANTIBOT" in response.content["message"]
    db.save_config.assert_not_called()


def test_create_accepts_a_legal_value(db):
    db.is_valid_setting.return_value = (True, "")

    response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_patch_rejects_a_value_the_setting_regex_forbids(db):
    db.is_valid_setting.side_effect = _rejecting("USE_ANTIBOT")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_ANTIBOT": "maybe"}))

    assert response.status_code == 400
    assert "USE_ANTIBOT" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_accepts_a_legal_value(db):
    db.is_valid_setting.return_value = (True, "")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_the_whole_payload_is_refused_when_one_key_is_invalid(db):
    """All-or-nothing: a partial silent apply is the defect this gate fixes."""

    db.is_valid_setting.side_effect = _rejecting("USE_ANTIBOT")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_REVERSE_PROXY": "yes", "USE_ANTIBOT": "maybe"}))

    assert response.status_code == 400
    assert "USE_ANTIBOT" in response.content["message"]
    assert "USE_REVERSE_PROXY" not in response.content["message"]
    db.save_config.assert_not_called()


def test_all_invalid_keys_are_reported_at_once(db):
    """One round-trip tells the caller everything that is wrong, not just the first thing."""

    db.is_valid_setting.side_effect = _rejecting("A_SETTING", "B_SETTING", "C_SETTING")

    response = ROUTER.update_service(
        SERVICE,
        schemas.ServiceUpdateRequest(variables={"A_SETTING": "1", "B_SETTING": "2", "C_SETTING": "3"}),
    )

    assert response.status_code == 400
    message = response.content["message"]
    assert message.startswith("Invalid settings: ")
    assert all(key in message for key in ("A_SETTING", "B_SETTING", "C_SETTING"))
    db.save_config.assert_not_called()


def test_a_pre_existing_invalid_row_does_not_block_the_save(db):
    """Validation applies to keys in THIS payload, not to rows stored before the gate existed."""

    db.get_non_default_settings.return_value = {"SERVER_NAME": SERVICE, f"{SERVICE}_OLD_BAD": "not-legal-anymore"}
    db.is_valid_setting.side_effect = _rejecting("OLD_BAD", f"{SERVICE}_OLD_BAD")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()
    validated = {call.args[0] for call in db.is_valid_setting.call_args_list}
    assert not any(key.endswith("OLD_BAD") for key in validated)


# --- how the keys are validated ---------------------------------------------------
# These pin the kwargs, not just the outcome. Getting them wrong disables the context
# check without failing any of the tests above.


def test_service_variables_are_validated_as_multisite(db):
    db.is_valid_setting.return_value = (True, "")

    ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={"USE_ANTIBOT": "captcha"}))

    assert db.is_valid_setting.call_args_list
    for call in db.is_valid_setting.call_args_list:
        # multisite=True is what makes a global-context key fail here, mirroring the gate
        # Configurator applies to `<service>_<KEY>`.
        assert call.kwargs["multisite"] is True
        # extra_services is only consulted when an already-prefixed key misses the plain
        # lookup, and that branch does not set multisite -- routing through it would
        # silently weaken the context check.
        assert "extra_services" not in call.kwargs
        # Keys stay unprefixed: prefixing is what would push the lookup into that branch.
        assert not call.args[0].startswith("new.example.com_")


def test_a_global_context_setting_is_refused_as_a_service_variable(db):
    """`GET /services/{svc}` echoes unprefixed global keys; feeding them back used to write
    a phantom row that GET returned and NGINX never saw."""

    def validate(setting, **_kwargs):
        return (False, "not multisite") if setting == "LOG_LEVEL" else (True, "")

    db.is_valid_setting.side_effect = validate

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"LOG_LEVEL": "debug"}))

    assert response.status_code == 400
    assert "LOG_LEVEL: not multisite" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_does_not_validate_server_name_from_variables(db):
    """update_service ignores SERVER_NAME inside `variables`, so gating it would be a 400
    on a write that never happens."""

    db.is_valid_setting.side_effect = _rejecting("SERVER_NAME")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"SERVER_NAME": "junk", "USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


# --- the server_name gate ---------------------------------------------------------
# An illegal name is not merely dropped: Configurator answers an invalid SERVER_NAME with
# exit(1), so NO config is regenerated for ANY service until the bad name is removed.


def test_create_rejects_an_illegal_server_name(db):
    db.is_valid_setting.side_effect = _rejecting("SERVER_NAME")

    response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="WWW.EXAMPLE.COM"))

    assert response.status_code == 400
    assert "Invalid server_name" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_rejects_an_illegal_rename(db):
    db.is_valid_setting.side_effect = _rejecting("SERVER_NAME")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(server_name="WWW.EXAMPLE.COM"))

    assert response.status_code == 400
    assert "Invalid server_name" in response.content["message"]
    db.save_config.assert_not_called()


# --- the USE_TEMPLATE referential gate --------------------------------------------
# USE_TEMPLATE holds an ORDERED LIST of template ids and its regex is `^.*$` -- it has to be,
# the ids are user-created -- so a typo clears the regex gate above and is only noticed at
# generation time, where it silently drops ONE LAYER OF N.


def test_create_rejects_an_unknown_template_layer(db):
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = [(2, "typo")]

    response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name="new.example.com", variables={"USE_TEMPLATE": "low typo"}))

    assert response.status_code == 400
    assert "USE_TEMPLATE" in response.content["message"]
    assert "typo" in response.content["message"]
    assert "position 2" in response.content["message"], "the operator needs the position, not just the id"
    db.save_config.assert_not_called()


def test_patch_rejects_an_unknown_template_layer(db):
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = [(1, "gone")]

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_TEMPLATE": "gone low"}))

    assert response.status_code == 400
    assert "position 1" in response.content["message"]
    db.save_config.assert_not_called()


def test_a_fully_known_template_list_is_accepted(db):
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = []

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_TEMPLATE": "low high"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_the_referential_check_runs_only_for_use_template(db):
    """One extra resolution per submitted USE_TEMPLATE, never per key."""
    db.is_valid_setting.return_value = (True, "")

    ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_ANTIBOT": "captcha", "USE_GZIP": "yes"}))

    db.unknown_template_layers.assert_not_called()


def test_a_key_failing_the_regex_gate_is_not_also_layer_checked(db):
    """The `continue` after the regex failure: reporting both reasons for one key is noise."""
    db.is_valid_setting.side_effect = _rejecting("USE_TEMPLATE")

    response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"USE_TEMPLATE": "low"}))

    assert response.status_code == 400
    db.unknown_template_layers.assert_not_called()
