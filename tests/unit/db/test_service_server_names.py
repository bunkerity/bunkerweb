"""Server names in the config read: a service is named by its id, and single-site keeps every name.

Two defects, one reader (``DatabaseConfigReadMixin``):

* A service with no ``SERVER_NAME`` row of its own inherited the GLOBAL value, because
  ``SERVER_NAME`` is a multisite setting and the multisite defaults are copied onto every service.
  The Linux ``variables.env`` ships ``SERVER_NAME=``, so such a service rendered ``server_name ;``
  and nginx refused the whole configuration. It is now named by its id (dev ``cea19bc67``).
* With ``MULTISITE=no`` the roster was rebuilt from the service ids, and a single-site service is
  keyed by the first name only, so ``SERVER_NAME="a.test b.test"`` read back as ``a.test``
  (dev ``513ac59fe``).
"""

from unittest.mock import Mock

import pytest

from fixtures.seed import add_global_value, add_service, add_service_setting, make_core_plugin, make_general_settings, seed_minimal, seed_multisite

APP1 = "app1.example.com"
APP2 = "app2.example.com"


class TestServiceWithoutOwnServerName:
    """`seed_multisite`: app1 and app2, neither with a SERVER_NAME row."""

    @pytest.mark.parametrize("global_value", ["", "global.example.com"], ids=["linux-empty-global", "named-global"])
    def test_get_config_names_the_service_by_its_id(self, db, global_value):
        seed_multisite(db)
        add_global_value(db, setting_id="SERVER_NAME", value=global_value)

        cfg = db.get_config(methods=False)

        assert cfg[f"{APP2}_SERVER_NAME"] == APP2
        assert cfg[f"{APP1}_SERVER_NAME"] == APP1

    @pytest.mark.parametrize("global_value", ["", "global.example.com"], ids=["linux-empty-global", "named-global"])
    def test_get_non_default_settings_names_the_service_by_its_id(self, db, global_value):
        seed_multisite(db)
        add_global_value(db, setting_id="SERVER_NAME", value=global_value)

        cfg = db.get_non_default_settings(methods=False)

        assert cfg[f"{APP2}_SERVER_NAME"] == APP2

    def test_the_default_of_the_setting_is_not_inherited_either(self, db):
        """No global row at all: the schema default (`www.example.com` in production) is not a name."""
        seed_multisite(db)

        assert db.get_config(methods=False)[f"{APP2}_SERVER_NAME"] == APP2

    def test_the_service_view_is_named_by_its_id(self, db):
        seed_multisite(db)
        add_global_value(db, setting_id="SERVER_NAME", value="")

        assert db.get_config(methods=False, service=APP2)["SERVER_NAME"] == APP2

    def test_an_own_row_still_wins(self, db):
        seed_multisite(db)
        add_service_setting(db, service_id=APP1, setting_id="SERVER_NAME", value=f"{APP1} alias.example.com")

        cfg = db.get_config(methods=False)

        assert cfg[f"{APP1}_SERVER_NAME"] == f"{APP1} alias.example.com"
        assert cfg[f"{APP2}_SERVER_NAME"] == APP2

    def test_a_template_cannot_name_a_service(self, db):
        """A template's SERVER_NAME is a placeholder: it would replace the id of every service using it."""
        seed_multisite(db)
        assert db.create_template("named", name="Named", settings={"SERVER_NAME": "tpl.example.com"}, steps=[{"title": "S", "settings": ["SERVER_NAME"]}]) == ""
        add_service_setting(db, service_id=APP2, setting_id="USE_TEMPLATE", value="named")

        assert db.get_config(methods=False)[f"{APP2}_SERVER_NAME"] == APP2


class TestSingleSiteKeepsEveryName:
    @pytest.fixture
    def single_site(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha")])
        db.initialize_db("1.7.0", "Docker")
        return db

    def test_every_server_name_entry_reads_back(self, single_site):
        db = single_site
        db.save_config({"MULTISITE": "no", "SERVER_NAME": "a.test b.test c.test"}, "scheduler")

        assert db.get_config(methods=False)["SERVER_NAME"] == "a.test b.test c.test"
        assert db.get_non_default_settings(methods=False)["SERVER_NAME"] == "a.test b.test c.test"

    def test_the_service_is_still_one_row_keyed_by_the_first_name(self, single_site):
        db = single_site
        db.save_config({"MULTISITE": "no", "SERVER_NAME": "a.test b.test"}, "scheduler")

        assert [service["id"] for service in db.get_services(with_drafts=True)] == ["a.test"]

    def test_a_single_name_is_unchanged(self, single_site):
        db = single_site
        db.save_config({"MULTISITE": "no", "SERVER_NAME": "a.test"}, "scheduler")

        assert db.get_config(methods=False)["SERVER_NAME"] == "a.test"

    def test_a_global_template_can_provide_the_names(self, db):
        """No stored SERVER_NAME: a template of the global USE_TEMPLATE list supplies it, the last layer first."""
        seed_minimal(db)
        for template, names in (("base", f"{APP1} base.test"), ("named", f"{APP1} alias.test")):
            assert db.create_template(template, name=template, settings={"SERVER_NAME": names}, steps=[{"title": "S", "settings": ["SERVER_NAME"]}]) == ""
        add_global_value(db, setting_id="USE_TEMPLATE", value="base named")

        assert db.get_config(methods=False)["SERVER_NAME"] == f"{APP1} alias.test"

    def test_names_that_do_not_start_with_the_service_id_are_not_used(self, db):
        """The stored names only extend the roster when the service IS the first of them: a stale
        global value must not rename a service that is keyed by something else."""
        seed_minimal(db)
        add_global_value(db, setting_id="SERVER_NAME", value="other.test b.test")

        assert db.get_config(methods=False)["SERVER_NAME"] == APP1

    def test_a_second_service_row_keeps_the_roster(self, db):
        """Two rows in single-site is not the one-service shape: the roster is the rows."""
        seed_minimal(db)
        add_service(db, APP2)
        add_global_value(db, setting_id="SERVER_NAME", value=f"{APP1} b.test")

        assert set(db.get_config(methods=False)["SERVER_NAME"].split()) == {APP1, APP2}


class TestSharedServerNameWarning:
    """nginx serves a name for one server block only: with two services on one name the second never
    answers. Autoconf and the scheduler cannot be refused (the Web UI and the API are, before they
    save), so the save says so (dev ``a3c2d81c8``)."""

    @pytest.fixture
    def saved(self, db, monkeypatch):
        db.init_tables([make_general_settings(), make_core_plugin("alpha")])
        db.initialize_db("1.7.0", "Docker")
        warning = Mock()
        monkeypatch.setattr(db.logger, "warning", warning)

        def save(method, **names):
            config = {"MULTISITE": "yes", "SERVER_NAME": " ".join(names)} | {f"{service}_SERVER_NAME": value for service, value in names.items()}
            db.save_config(config, method)
            return [call.args[0] for call in warning.call_args_list]

        return save

    @pytest.mark.parametrize("method", ["scheduler", "autoconf"])
    def test_two_services_on_one_name_are_warned_about(self, saved, method):
        messages = saved(method, **{"a.test": "a.test shared.test", "b.test": "b.test shared.test"})

        assert any("shared.test" in message and "used by both services a.test and b.test" in message for message in messages), messages

    def test_distinct_names_are_not_warned_about(self, saved):
        messages = saved("scheduler", **{"a.test": "a.test a-alias.test", "b.test": "b.test"})

        assert not any("used by both" in message for message in messages), messages

    @pytest.mark.parametrize("method", ["ui", "api"])
    def test_the_web_ui_and_the_api_are_not_warned_twice(self, saved, method):
        messages = saved(method, **{"a.test": "a.test shared.test", "b.test": "b.test shared.test"})

        assert not any("used by both" in message for message in messages), messages
