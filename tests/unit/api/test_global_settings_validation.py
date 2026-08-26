"""The global settings write path must validate before saving.

Follows the module-loader + stubbed-``sys.modules`` pattern established by
``test_api_upstreams.py``/``test_api_web_cache.py``: there is no live FastAPI
``TestClient`` in ``tests/unit/api``, so the router function is called directly against a
``Mock`` db.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import schemas  # type: ignore
from Database import Database  # type: ignore

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    put = get
    patch = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_global_settings": ModuleType("bw_global_settings"),
        "bw_global_settings.routers": ModuleType("bw_global_settings.routers"),
        "bw_global_settings.auth": ModuleType("bw_global_settings.auth"),
        "bw_global_settings.auth.guard": ModuleType("bw_global_settings.auth.guard"),
        "bw_global_settings.schemas": schemas,
        "bw_global_settings.utils": ModuleType("bw_global_settings.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_global_settings"].__path__ = []
    names["bw_global_settings.routers"].__path__ = []
    names["bw_global_settings.auth"].__path__ = []
    names["bw_global_settings.auth.guard"].guard = object()
    names["bw_global_settings.utils"].get_db = Mock()
    names["bw_global_settings.utils"].LOGGER = Mock()
    # `http01.py` is loaded for real, not stubbed: it holds the shared refusal core both routers
    # now import, and a stub of it would make every assertion below assert the stub.
    http01_spec = importlib.util.spec_from_file_location("bw_global_settings.http01", ROOT / "src" / "api" / "app" / "http01.py")
    http01 = importlib.util.module_from_spec(http01_spec)
    http01_spec.loader.exec_module(http01)
    names["bw_global_settings.http01"] = http01
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "global_settings.py"
        spec = importlib.util.spec_from_file_location("bw_global_settings.routers.global_settings", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    # Empty by default: no pre-existing API-managed overrides to merge into the save.
    fake_db.get_non_default_settings.return_value = {}
    # The ownership gate must be exercised against the real compatibility rule, not a Mock
    # (a Mock return value is truthy, i.e. "always compatible", which would hide the gate).
    fake_db._methods_are_compatible = Database._methods_are_compatible
    # Same reason as above: a bare Mock is truthy, which the USE_TEMPLATE gate would read as
    # "every layer is unknown" and reject every save.
    fake_db.unknown_template_layers.return_value = []
    # The declared-default fallback the http-01 gate reaches for when the snapshot carries no
    # global port row (`get_config` default-fills from `bw_settings.default`).
    fake_db.get_config.return_value = {"HTTP_PORT": "8080"}
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def test_patch_rejects_a_value_the_setting_regex_forbids(db):
    db.is_valid_setting.return_value = (False, "not matching regex: '^(no|cookie|captcha)$'")

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "yes"}))

    assert response.status_code == 400
    assert "USE_ANTIBOT" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_accepts_a_legal_value(db):
    db.is_valid_setting.return_value = (True, "")
    db.save_config.return_value = set()

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_a_legacy_invalid_value_on_an_untouched_key_does_not_block_the_save(db):
    """Validation applies to keys in THIS payload, not to pre-existing rows."""

    # A previously-stored, now-illegal value on a key absent from this payload.
    db.get_non_default_settings.return_value = {
        "OLD_BAD_SETTING": {"value": "not-legal-anymore", "method": "api"},
    }

    def validate(setting, **_kwargs):
        return (False, "legacy") if setting == "OLD_BAD_SETTING" else (True, "")

    db.is_valid_setting.side_effect = validate
    db.save_config.return_value = set()

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()
    # is_valid_setting must never have been asked about the untouched legacy key.
    validated_keys = {call.args[0] for call in db.is_valid_setting.call_args_list}
    assert "OLD_BAD_SETTING" not in validated_keys


# --- ownership gate ---------------------------------------------------------------
# save_config silently skips a row whose method 'api' may not take over, so without this
# gate the endpoint answered 200 "success" having written nothing at all.


@pytest.fixture
def writable_db(db):
    """A db that accepts every value and every save — leaves ownership as the only variable."""
    db.is_valid_setting.return_value = (True, "")
    db.save_config.return_value = set()
    return db


@pytest.mark.parametrize("owner", ("scheduler", "autoconf"))
def test_patch_refuses_a_key_owned_by_a_method_api_cannot_overwrite(writable_db, owner):
    writable_db.get_non_default_settings.return_value = {"USE_ANTIBOT": {"value": "no", "method": owner}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 409
    assert "USE_ANTIBOT" in response.content["message"]
    assert owner in response.content["message"]
    writable_db.save_config.assert_not_called()


@pytest.mark.parametrize("owner", ("ui", "api"))
def test_patch_overwrites_a_key_owned_by_an_interchangeable_method(writable_db, owner):
    """ui and api are interchangeable per Database._methods_are_compatible."""

    writable_db.get_non_default_settings.return_value = {"USE_ANTIBOT": {"value": "no", "method": owner}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


def test_patch_accepts_a_key_that_has_no_row_yet(writable_db):
    """No entry means no Global_values row, so save_config INSERTs it whatever the method."""

    writable_db.get_non_default_settings.return_value = {"SOMETHING_ELSE": {"value": "x", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


def test_patch_refuses_the_whole_payload_when_one_key_is_owned_elsewhere(writable_db):
    """All-or-nothing: a partial silent apply is the defect this gate fixes."""

    writable_db.get_non_default_settings.return_value = {
        "USE_ANTIBOT": {"value": "no", "method": "scheduler"},
        "USE_REVERSE_PROXY": {"value": "no", "method": "api"},
    }

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_REVERSE_PROXY": "yes", "USE_ANTIBOT": "captcha"}))

    assert response.status_code == 409
    assert "USE_ANTIBOT (scheduler)" in response.content["message"]
    assert "USE_REVERSE_PROXY" not in response.content["message"]
    writable_db.save_config.assert_not_called()


def test_patch_of_a_foreign_owned_key_already_at_the_requested_value_is_not_a_conflict(writable_db):
    """Ownership alone is not a refused write — save_config gates its refusal on `value_changed`.

    If the row already holds what the caller is asking for, nothing was going to be written and
    nothing was silently dropped, so the 200 is truthful. Conflicting on ownership alone broke the
    canonical merge-PATCH flow (GET the config, edit one key, PATCH the whole dict back), which in
    Docker/compose carries a scheduler-owned value for nearly every non-default global.
    """

    writable_db.get_non_default_settings.return_value = {"LOG_LEVEL": {"value": "info", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"LOG_LEVEL": "info"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


def test_patch_refuses_a_suffix_zero_key_whose_row_is_keyed_plainly(writable_db):
    """`FOO_0` must resolve to the plainly-keyed row, or it slips the gate and gets a false 200.

    get_non_default_settings appends the suffix only when the setting is `multiple` AND the suffix
    is > 0, so a suffix-0 row comes back as `WHITELIST_URL`. save_config's SUFFIX_RX resolves the
    payload key `WHITELIST_URL_0` to that same row and then drops the write.
    """

    writable_db.get_non_default_settings.return_value = {"WHITELIST_URL": {"value": "http://a", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"WHITELIST_URL_0": "http://b"}))

    assert response.status_code == 409
    assert "WHITELIST_URL_0 (scheduler)" in response.content["message"]
    writable_db.save_config.assert_not_called()


def test_patch_does_not_mistake_a_double_digit_suffix_for_suffix_zero(writable_db):
    """`FOO_10` ends in a '0' but is keyed with its suffix, so it must not be truncated to `FOO_1`."""

    writable_db.get_non_default_settings.return_value = {"WHITELIST_URL_10": {"value": "http://a", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"WHITELIST_URL_10": "http://b"}))

    assert response.status_code == 409
    assert "WHITELIST_URL_10 (scheduler)" in response.content["message"]


def test_patch_does_not_let_the_synthetic_server_name_method_trigger_a_conflict(writable_db):
    """get_non_default_settings always reports SERVER_NAME as method='scheduler' (it overwrites
    the entry with the service list), so the gate must skip it or every payload carrying
    SERVER_NAME would 409 on a method that is not the row's real owner."""

    writable_db.get_non_default_settings.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"SERVER_NAME": "app.example.com other.example.com"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


# --- the USE_TEMPLATE referential gate --------------------------------------------


def test_patch_rejects_an_unknown_global_template_layer(db):
    """A global USE_TEMPLATE is the fallback for every service without its own, so a typo here
    drops a layer fleet-wide. Its regex is `^.*$`, so only a referential check can catch it."""
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = [(2, "typo")]

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_TEMPLATE": "low typo"}))

    assert response.status_code == 400
    assert "USE_TEMPLATE" in response.content["message"]
    assert "position 2" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_accepts_a_fully_known_global_template_list(db):
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = []
    db.save_config.return_value = set()

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_TEMPLATE": "low high"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_the_layer_check_runs_only_for_use_template(db):
    db.is_valid_setting.return_value = (True, "")
    db.save_config.return_value = set()

    ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    db.unknown_template_layers.assert_not_called()


# --- the fleet-wide HTTP-01 gate --------------------------------------------------


class TestAGlobalHttp01WriteMayNotStrandAService:
    """``POST``/``PATCH /services`` has refused this per service since ``HTTP_PORT`` became
    multisite, but the two paths that write the same settings FLEET-WIDE did not: a global
    ``LETS_ENCRYPT_CHALLENGE=http`` reached a service that had been moved off the fleet's HTTP
    listener and failed sixty seconds later inside the certificate job, against a rate-limited
    ACME account, with nobody watching.

    A global write differs from a single-service one in what it must report: it can strand many
    services at once, so every offending one is named -- being told about the first of five means
    fixing it and being refused again four times.
    """

    MOVED = "moved.example.com"
    ALIGNED = "aligned.example.com"

    def _snapshot(self, **extra):
        """A fleet on 8080 with one service that declared a port of its own."""
        config = {
            "SERVER_NAME": f"{self.ALIGNED} {self.MOVED}",
            "MULTISITE": "yes",
            "HTTP_PORT": "8080",
            f"{self.MOVED}_HTTP_PORT": "9080",
        }
        config.update(extra)
        return config

    def _wire(self, db, snapshot, rows=None):
        """``_current_api_global_overrides`` and the http-01 gate both call
        ``get_non_default_settings``; only the first asks for ``methods``."""

        def get_non_default_settings(**kwargs):
            return dict(rows or {}) if kwargs.get("methods") else dict(snapshot)

        db.get_non_default_settings.side_effect = get_non_default_settings

    def test_turning_on_the_http_challenge_globally_is_refused(self, writable_db):
        self._wire(writable_db, self._snapshot(AUTO_LETS_ENCRYPT="yes"))

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"LETS_ENCRYPT_CHALLENGE": "http"}))

        assert response.status_code == 400
        message = response.content["message"]
        assert self.MOVED in message, message
        assert "9080" in message and "8080" in message, message
        assert "LETS_ENCRYPT_CHALLENGE=dns" in message, message
        writable_db.save_config.assert_not_called()

    def test_turning_on_lets_encrypt_globally_is_refused_too(self, writable_db):
        """``LETS_ENCRYPT_CHALLENGE`` defaults to ``http``, so ``AUTO_LETS_ENCRYPT=yes`` alone
        arms the challenge -- the payload never has to mention it."""
        self._wire(writable_db, self._snapshot())

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"AUTO_LETS_ENCRYPT": "yes"}))

        assert response.status_code == 400
        assert self.MOVED in response.content["message"]
        writable_db.save_config.assert_not_called()

    def test_a_clean_fleet_still_passes(self, writable_db):
        """Anti-vacuity, and the contract for every existing deployment: no service moved, so the
        same write goes through exactly as before the gate existed."""
        snapshot = self._snapshot()
        del snapshot[f"{self.MOVED}_HTTP_PORT"]
        self._wire(writable_db, snapshot)

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http"}))

        assert response.status_code == 200
        writable_db.save_config.assert_called_once()

    def test_every_stranded_service_is_named(self, writable_db):
        second = "other.example.com"
        snapshot = self._snapshot(AUTO_LETS_ENCRYPT="yes")
        snapshot["SERVER_NAME"] = f"{self.ALIGNED} {self.MOVED} {second}"
        snapshot[f"{second}_HTTP_PORT"] = "9081"
        self._wire(writable_db, snapshot)

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"LETS_ENCRYPT_CHALLENGE": "http"}))

        assert response.status_code == 400
        message = response.content["message"]
        assert self.MOVED in message and second in message, message
        assert self.ALIGNED not in message, message

    def test_moving_the_fleet_port_strands_a_service_that_spelled_out_the_old_one(self, writable_db):
        """The other direction, and the reason ``HTTP_PORT`` is in the trigger set: the service
        did not move, the fleet did -- and the service now differs from it just the same."""
        self._wire(writable_db, self._snapshot(AUTO_LETS_ENCRYPT="yes", **{f"{self.MOVED}_HTTP_PORT": "8080"}))

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"HTTP_PORT": "9080"}))

        assert response.status_code == 400
        assert self.MOVED in response.content["message"]
        writable_db.save_config.assert_not_called()

    def test_a_service_using_the_dns_challenge_is_left_alone(self, writable_db):
        self._wire(writable_db, self._snapshot(AUTO_LETS_ENCRYPT="yes", **{f"{self.MOVED}_LETS_ENCRYPT_CHALLENGE": "dns"}))

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"LETS_ENCRYPT_CHALLENGE": "http"}))

        assert response.status_code == 200
        writable_db.save_config.assert_called_once()

    def test_a_stock_fleet_can_still_turn_lets_encrypt_on(self, writable_db):
        """No global ``HTTP_PORT`` row (nobody moved it) and no service override either -- the
        commonest fleet there is, and the one this endpoint's whole purpose is to serve.

        The declared-default recovery used to be added to the GLOBAL side of the comparison only,
        so every service's empty port list read as moved off ``['8080']`` and a plain
        ``AUTO_LETS_ENCRYPT=yes`` was refused fleet-wide with "it listens on its own HTTP port(s)
        (none)". The default now reaches both sides."""
        self._wire(writable_db, {"SERVER_NAME": f"{self.ALIGNED} {self.MOVED}", "MULTISITE": "yes"})

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"AUTO_LETS_ENCRYPT": "yes"}))

        assert response.status_code == 200, response.content
        writable_db.save_config.assert_called_once()

    def test_an_unrelated_payload_reads_no_snapshot(self, writable_db):
        """The gate is the one check here that is not payload-only, so it has to stay off the
        common path: a payload that cannot change the answer must not pay a full config read.
        ``_current_api_global_overrides`` is the only other caller, hence exactly one call."""
        self._wire(writable_db, self._snapshot(AUTO_LETS_ENCRYPT="yes"))

        response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

        assert response.status_code == 200
        assert writable_db.get_non_default_settings.call_count == 1


class TestTheConfigPutIsGatedTheSameWay:
    """``PUT /global_settings/config`` is the autoconf settings-apply path
    (``autoconf/Config.py:apply`` -> ``AutoconfApiClient.save_config``) and the UI's config
    editor. Its payload is the COMPLETE desired state, so unlike the PATCH above there is nothing
    to merge -- but it wrote the same stranding combination with no check at all.

    Detection is asserted here through an INTERACTIVE caller, where the answer is a refusal. What
    the two callers then do with that answer is ``TestTheAutoconfCallerIsWarnedNotRefused``.
    """

    MOVED = "moved.example.com"

    def _config(self, **extra):
        config = {
            "SERVER_NAME": self.MOVED,
            "MULTISITE": "yes",
            "HTTP_PORT": "8080",
            f"{self.MOVED}_HTTP_PORT": "9080",
            "AUTO_LETS_ENCRYPT": "yes",
        }
        config.update(extra)
        return config

    def _put(self, config, method="ui"):
        return ROUTER.save_config(schemas.SaveConfigRequest(config=config, method=method))

    def test_a_config_that_strands_a_service(self, writable_db):
        response = self._put(self._config())

        assert response.status_code == 400
        message = response.content["message"]
        assert self.MOVED in message and "9080" in message, message
        writable_db.save_config.assert_not_called()

    def test_a_config_that_strands_nothing_is_saved(self, writable_db):
        config = self._config()
        del config[f"{self.MOVED}_HTTP_PORT"]

        response = self._put(config)

        assert response.status_code == 200
        writable_db.save_config.assert_called_once()

    def test_a_config_shaped_the_way_autoconf_builds_one(self, writable_db):
        """The real autoconf PAYLOAD shape, which is orthogonal to the caller.
        ``Config.__get_full_env`` emits ``SERVER_NAME``, ``MULTISITE`` and one PREFIXED key per
        container label -- there is no global ``AUTO_LETS_ENCRYPT`` and no global ``HTTP_PORT``
        row at all, so a trigger that only looked at unprefixed keys would wave through exactly
        the shape this gate was added for. The fleet's port comes from the declared default
        instead (``get_config``)."""
        response = self._put(self._autoconf_shaped())

        assert response.status_code == 400, response.content
        assert self.MOVED in response.content["message"]
        writable_db.save_config.assert_not_called()

    def test_a_prefixed_port_list_repetition_still_triggers_the_check(self, writable_db):
        """``<service>_HTTP_PORT_1`` -- a prefix AND a numeric suffix on the same key."""
        config = self._autoconf_shaped()
        del config[f"{self.MOVED}_HTTP_PORT"]
        config[f"{self.MOVED}_HTTP_PORT_1"] = "9081"

        response = self._put(config)

        assert response.status_code == 400, response.content
        assert "9081" in response.content["message"]

    def test_a_config_with_no_lets_encrypt_at_all_is_saved(self, writable_db):
        """The moved service is still there; nothing asks it to answer a challenge."""
        config = self._config()
        del config["AUTO_LETS_ENCRYPT"]

        response = self._put(config)

        assert response.status_code == 200
        writable_db.save_config.assert_called_once()

    def _autoconf_shaped(self):
        return {
            "SERVER_NAME": self.MOVED,
            "MULTISITE": "yes",
            f"{self.MOVED}_HTTP_PORT": "9080",
            f"{self.MOVED}_AUTO_LETS_ENCRYPT": "yes",
        }


class TestTheAutoconfCallerIsWarnedNotRefused(TestTheConfigPutIsGatedTheSameWay):
    """The one place the answer is not a refusal.

    ``autoconf`` is a declarative reconciler with no operator in the loop, and its payload is the
    WHOLE fleet: refusing it leaves every OTHER service unconfigured too -- on a first boot,
    nothing at all -- because one container carries a bad label. That trades one service's
    certificate failure for a fleet-wide outage, which is worse than the defect being fixed. So
    the same message is logged and the configuration is saved unchanged: the offending service's
    order fails exactly as it does today, no worse, and the operator gets the diagnostic at apply
    time instead of sixty seconds later inside a job.

    Inherits the class above so every detection case is re-run through the autoconf caller too --
    the shapes must be recognised identically; only the response differs.
    """

    @pytest.fixture(autouse=True)
    def logger(self, monkeypatch):
        fake = Mock()
        monkeypatch.setattr(ROUTER, "LOGGER", fake)
        return fake

    def _put(self, config, method="autoconf"):
        return ROUTER.save_config(schemas.SaveConfigRequest(config=config, method=method))

    def test_a_config_that_strands_a_service(self, writable_db, logger):
        """Same payload as the parent, opposite outcome: saved, and loudly."""
        response = self._put(self._config())

        assert response.status_code == 200, response.content
        writable_db.save_config.assert_called_once()
        logged = " ".join(str(call) for call in logger.error.call_args_list)
        assert self.MOVED in logged and "9080" in logged, logged
        assert "LETS_ENCRYPT_CHALLENGE=dns" in logged, logged

    def test_a_config_shaped_the_way_autoconf_builds_one(self, writable_db, logger):
        response = self._put(self._autoconf_shaped())

        assert response.status_code == 200, response.content
        writable_db.save_config.assert_called_once()
        assert self.MOVED in " ".join(str(call) for call in logger.error.call_args_list)

    def test_a_prefixed_port_list_repetition_still_triggers_the_check(self, writable_db, logger):
        config = self._autoconf_shaped()
        del config[f"{self.MOVED}_HTTP_PORT"]
        config[f"{self.MOVED}_HTTP_PORT_1"] = "9081"

        response = self._put(config)

        assert response.status_code == 200, response.content
        writable_db.save_config.assert_called_once()
        assert "9081" in " ".join(str(call) for call in logger.error.call_args_list)

    def test_the_config_is_saved_exactly_as_it_arrived(self, writable_db, logger):
        """Warn, never repair. A reconciler that quietly moved the port back or switched the
        challenge would be deciding what the operator meant."""
        config = self._autoconf_shaped()

        self._put(dict(config))

        saved = writable_db.save_config.call_args[0][0]
        assert saved == config, saved

    def test_a_clean_autoconf_config_logs_nothing(self, writable_db, logger):
        """Anti-vacuity for the log assertions above: the ERROR is not emitted unconditionally."""
        config = self._autoconf_shaped()
        del config[f"{self.MOVED}_HTTP_PORT"]

        response = self._put(config)

        assert response.status_code == 200
        writable_db.save_config.assert_called_once()
        logger.error.assert_not_called()
