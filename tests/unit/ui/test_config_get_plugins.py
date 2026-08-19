"""UI `Config.get_plugins` — the shape it returns, and what it must not do to get there.

This method reshapes the API's plugin *list* into a dict keyed by id. It used to do that with
`plugin.pop("id")`, editing the API client's own response in place. That was invisible while
every call meant a fresh HTTP response; with the per-request GET memo (Lot B) the second caller
in a render gets the same objects, so the pages that resolve a plugin after the shared context
has already listed them — `/global-settings/plugins/<p>`, `/services/<s>/plugins/<p>` — died with
`KeyError: 'id'`.
"""

from unittest.mock import Mock

from app.models.config import Config  # type: ignore  (src/ui on path via ui conftest)

RECORDS = [
    {"id": "antibot", "name": "Antibot", "type": "core", "settings": {"USE_ANTIBOT": {}}},
    {"id": "redis", "name": "Redis", "type": "core", "settings": {}},
]


def _config(records):
    cfg = Config.__new__(Config)  # skip __init__ (it reads the hardcoded settings.json path)
    client = Mock()
    client.get_plugins.return_value = records
    cfg._Config__api_client = client
    return cfg, client


def test_records_are_keyed_by_id_with_general_first():
    cfg, _ = _config([dict(record) for record in RECORDS])

    plugins = cfg.get_plugins()

    assert list(plugins) == ["general", "antibot", "redis"]
    assert plugins["antibot"]["name"] == "Antibot"
    assert "id" not in plugins["antibot"], "the id is the key; repeating it in the value is what the pop was for"


def test_the_api_response_is_left_intact():
    """The response may be a memo entry shared with the rest of this request."""
    records = [dict(record) for record in RECORDS]
    cfg, _ = _config(records)

    cfg.get_plugins()

    assert records == RECORDS


def test_two_calls_in_one_request_agree():
    """The regression that shipped: identical input, identical output, however many times."""
    cfg, _ = _config([dict(record) for record in RECORDS])

    assert cfg.get_plugins() == cfg.get_plugins()


def test_the_slim_shape_is_passed_through_to_the_client():
    cfg, client = _config([])

    cfg.get_plugins(with_settings=False)

    assert client.get_plugins.call_args.kwargs["with_settings"] is False
