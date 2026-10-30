"""Creating or deleting a service must not rewrite the other services (#3986).

``new_service`` and ``delete_service`` seeded ``gen_conf`` with the whole stored config. That config carries each service's
inherited global value, which ``gen_conf`` keeps over the template-aware value from ``get_services``, so a setting a service
took from its template was saved back as an explicit service row. Both now seed with the global config only, like ``edit_service``.
"""

from unittest.mock import MagicMock

import pytest

from app.models.config import Config

SETTINGS = {
    "SERVER_NAME": {"context": "multisite", "regex": ".*", "type": "text"},
    "USE_X": {"context": "multisite", "regex": "^(yes|no)$", "type": "check"},
    "LOG_LEVEL": {"context": "global", "regex": ".*", "type": "text"},
    "IS_DRAFT": {"context": "multisite", "regex": "^(yes|no)$", "type": "check"},
}

# What the database would answer: the full config holds b.com's inherited global fallback ("no"), the global-only one never does.
GLOBAL = {"LOG_LEVEL": "info", "SERVER_NAME": "b.com"}
FULL = GLOBAL | {"b.com_SERVER_NAME": "b.com", "b.com_USE_X": "no"}


@pytest.fixture
def cfg():
    db = MagicMock(name="db")
    db.database_uri = "sqlite:///db"
    db.save_config.return_value = set()
    db.get_plugins.return_value = [{"id": "general", "settings": {}}]
    # b.com takes USE_X=yes from its template; get_services is the template-aware view
    db.get_services_settings.return_value = [{"SERVER_NAME": "b.com", "USE_X": "yes"}, {"SERVER_NAME": "c.com", "USE_X": "no"}]
    db.get_non_default_settings.side_effect = lambda global_only=False, **kwargs: dict(GLOBAL if global_only else FULL)
    config = Config.__new__(Config)
    config._Config__settings = dict(SETTINGS)
    config._Config__db = db
    config._Config__data = {}
    config._Config__ignore_regex_check = False
    config._Config__plugins_cache = {}
    config.db = db
    return config


def test_issue_3986_creating_a_service_keeps_the_template_value_of_the_others(cfg):
    """The saved config holds b.com's template-aware ``yes``, not the stale inherited ``no`` (#3986)."""
    assert cfg.new_service({"SERVER_NAME": "n.com"}) == ("Configuration for n.com has been generated.", 0)

    conf = cfg.db.save_config.call_args.args[0]
    assert conf["b.com_USE_X"] == "yes"
    assert cfg.db.get_non_default_settings.call_args.kwargs["global_only"] is True


def test_issue_3986_deleting_a_service_keeps_the_template_value_of_the_others(cfg):
    """Deleting c.com leaves b.com's template-aware ``yes`` in the saved config (#3986)."""
    cfg.db.get_services_settings.return_value = [{"SERVER_NAME": "b.com", "USE_X": "yes"}, {"SERVER_NAME": "c.com", "USE_X": "no"}]
    cfg.db.get_non_default_settings.side_effect = lambda global_only=False, **kwargs: dict(
        {"LOG_LEVEL": "info", "SERVER_NAME": "b.com c.com"} if global_only else FULL | {"SERVER_NAME": "b.com c.com", "c.com_SERVER_NAME": "c.com"}
    )

    assert cfg.delete_service("c.com") == ("Configuration for c.com has been deleted.", 0)

    conf = cfg.db.save_config.call_args.args[0]
    assert conf["SERVER_NAME"] == "b.com" and conf["b.com_USE_X"] == "yes"
    assert not any(key.startswith("c.com") for key in conf)
