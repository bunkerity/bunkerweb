"""Each config-write rejection must discard the submitted value and explain why."""

import pytest

from test_config_check_variables import _config


@pytest.mark.parametrize(
    "key,value,settings,stored,message",
    [
        ("DATABASE_URI", "changed", {"DATABASE_URI": {}}, {}, "Variable DATABASE_URI is not editable, ignoring it."),
        ("UNKNOWN", "changed", {}, {}, "Variable UNKNOWN is not valid."),
        ("UNKNOWN_1", "changed", {}, {}, "Variable UNKNOWN_1 is not valid."),
        ("TXT_1", "changed", {"TXT": {}}, {}, "Variable TXT_1 is not valid."),
        ("TXT_bad", "changed", {"TXT": {"multiple": "value"}}, {}, "Variable TXT_bad is not valid."),
        (
            "TXT",
            "changed",
            {"TXT": {}},
            {"TXT": {"value": "original", "method": "env", "global": False}},
            "Variable TXT is not editable as it is managed by the env, ignoring it.",
        ),
        ("SERVER_NAME", "", {"SERVER_NAME": {}}, {}, "The server name of a service can't be empty."),
        ("SERVER_NAME", " \t ", {"SERVER_NAME": {}}, {}, "The server name of a service can't be empty."),
        ("TXT", "first\nsecond", {"TXT": {}}, {}, "Value of TXT contains a newline."),
        ("TXT", "first\rsecond", {"TXT": {}}, {}, "Value of TXT contains a newline."),
        ("TXT", "invalid", {"TXT": {"regex": "^valid$"}}, {}, "Variable TXT is not valid."),
        (
            "TXT",
            "changed",
            {"TXT": {"regex": "["}},
            {},
            "Invalid regex for setting TXT: [. Ignoring regex check: unterminated character set at position 0",
        ),
    ],
    ids=[
        "blacklist",
        "unknown-name",
        "unknown-base",
        "non-multiple-suffix",
        "non-numeric-suffix",
        "env-managed",
        "empty-service-name",
        "blank-service-name",
        "embedded-lf",
        "embedded-cr",
        "regex-mismatch",
        "malformed-regex",
    ],
)
def test_rejected_variable_is_removed(key, value, settings, stored, message):
    # Keep every other gate permissive so each case isolates its own rejection.
    cfg = _config({name: {"type": "text", "regex": r"^[\s\S]*$", **schema} for name, schema in settings.items()})
    variables = {key: value, "UNCHANGED": "keep"}

    result = cfg.check_variables(variables, config=stored, to_check={key: value}, threaded=True)

    assert (result, cfg._Config__data["TO_FLASH"]) == ({"UNCHANGED": "keep"}, [{"content": message, "type": "error"}])


@pytest.mark.parametrize(
    "key,value,schema,stored,options",
    [
        ("TXT_1", "changed", {"type": "text", "multiple": "value"}, {}, {}),
        ("TXT", "first\nsecond\rthird", {"type": "file"}, {}, {}),
        ("TXT", "changed", {"type": "text"}, {"TXT": {"method": "ui", "global": False}}, {}),
        ("TXT", "changed", {"type": "text"}, {"TXT": {"method": "api", "global": False}}, {}),
        ("TXT", "changed", {"type": "text"}, {"TXT": {"method": "default", "global": False}}, {}),
        ("TXT", "changed", {"type": "text"}, {"TXT": {"method": "env", "global": True}}, {}),
        ("TXT", "changed", {"type": "text"}, {"TXT": {"method": "env", "global": False}}, {"new": True}),
    ],
    ids=["numeric-suffix", "multiline-file", "ui-managed", "api-managed", "default-managed", "service-overrides-global", "new-service"],
)
def test_allowed_value_survives_validation(key, value, schema, stored, options):
    cfg = _config({"TXT": {"regex": "^.*$", **schema}})

    result = cfg.check_variables({key: value}, config=stored, to_check={key: value}, threaded=True, **options)

    assert (result, cfg._Config__data["TO_FLASH"]) == ({key: value}, [])
