"""`CROWDSEC_CAPTCHA_PROVIDER` reaches the rendered bouncer configuration, and widens BOUNCING_ON_TYPE.

The setting is read at request time straight from the datastore (`crowdsec.lua`), so the only thing
the rendered `misc/crowdsec.conf` needs it for is `BOUNCING_ON_TYPE`. That one line decides whether
the bouncer ever *fetches* a `captcha` decision from the local API: upstream ships `ban`, and with
`ban` a captcha decision is never cached and the whole delegation is dead code.

Both halves are load-bearing and neither is visible from the other:

* the template variable only exists because `SETTINGS` in `crowdsec_conf_utils.py` lists it. Jinja's
  default undefined is *falsy but not equal to anything*, so a missing entry does not raise -- it
  silently renders `all` for everybody, including the operator who set the setting to `no` to keep
  the previous behaviour.
* `BOUNCING_ON_TYPE` accepts exactly one of `ban|captcha|all` (`lib/config.lua`); anything else is
  logged and replaced by `ban`. So the widened value has to be `all`, not a list.

The shipped template and the shipped settings table are both loaded from disk -- no copy.
"""

import importlib.util
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src" / "common" / "core" / "crowdsec"
CONF_UTILS = PLUGIN / "jobs" / "crowdsec_conf_utils.py"

# lib/config.lua's valid_bouncing_on_type_values -- kept here so widening the template to a value
# the parser rejects fails this test instead of failing silently at runtime with a default of "ban".
VALID_BOUNCING_ON_TYPE = {"ban", "captcha", "all"}


def load_conf_utils():
    spec = importlib.util.spec_from_file_location("crowdsec_conf_utils", CONF_UTILS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONF_UTILS_MODULE = load_conf_utils()


def render(env: dict, service: str = "") -> str:
    template = Environment(loader=FileSystemLoader(PLUGIN / "misc")).get_template("crowdsec.conf")
    return template.render(**CONF_UTILS_MODULE.render_variables(env.get, service))


def line(rendered: str, key: str) -> str:
    for entry in rendered.splitlines():
        if entry.startswith(key + "="):
            return entry.split("=", 1)[1]
    raise AssertionError(f"{key}= missing from:\n{rendered}")


class TestBouncingOnTypeFollowsTheSetting:
    def test_the_default_bounces_on_captcha_decisions_too(self):
        assert line(render({}), "BOUNCING_ON_TYPE") == "all"

    def test_opting_out_restores_the_previous_behaviour(self):
        assert line(render({"CROWDSEC_CAPTCHA_PROVIDER": "no"}), "BOUNCING_ON_TYPE") == "ban"

    def test_a_service_can_opt_out_on_its_own(self):
        env = {"CROWDSEC_CAPTCHA_PROVIDER": "captcha", "app.example.com_CROWDSEC_CAPTCHA_PROVIDER": "no"}
        assert line(render(env, "app.example.com"), "BOUNCING_ON_TYPE") == "ban"
        assert line(render(env, "other.example.com"), "BOUNCING_ON_TYPE") == "all"

    @pytest.mark.parametrize("provider", ["captcha", "javascript", "cookie", "capjs", "no"])
    def test_the_rendered_value_is_one_the_bouncer_parser_accepts(self, provider):
        assert line(render({"CROWDSEC_CAPTCHA_PROVIDER": provider}), "BOUNCING_ON_TYPE") in VALID_BOUNCING_ON_TYPE


class TestTheSettingIsWiredIntoTheTemplateVariables:
    def test_the_default_matches_plugin_json(self):
        from json import loads

        plugin = loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
        assert CONF_UTILS_MODULE.SETTINGS["CROWDSEC_CAPTCHA_PROVIDER"] == plugin["settings"]["CROWDSEC_CAPTCHA_PROVIDER"]["default"]

    def test_dropping_the_settings_entry_silently_ignores_the_opt_out(self, monkeypatch):
        """Mutation: without the SETTINGS entry Jinja hands the template an Undefined.

        `Undefined != "no"` is True, so the template renders `all` for an operator who explicitly
        asked for `no` -- no exception, no log line, just the behaviour change they opted out of.
        """
        settings = dict(CONF_UTILS_MODULE.SETTINGS)
        settings.pop("CROWDSEC_CAPTCHA_PROVIDER")
        monkeypatch.setattr(CONF_UTILS_MODULE, "SETTINGS", settings)
        assert line(render({"CROWDSEC_CAPTCHA_PROVIDER": "no"}), "BOUNCING_ON_TYPE") == "all"
