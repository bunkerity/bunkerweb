"""A custom config named ``0`` reached the database as the integer ``0``, which MariaDB matched against every name.

Pins that the delete route refuses a selection whose name is not a string, and that the digit-only
string itself still goes through as the exact key.
"""

import json

import pytest


@pytest.fixture
def cfg(h):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com"}
    h.db.get_custom_configs.return_value = []
    h.db.delete_custom_configs.return_value = ("", {(None, "http", "0")}, set())
    return h.routes.configs


@pytest.mark.parametrize("name", [0, 7, 1.5, True])
def test_delete_refuses_a_non_string_name(h, cfg, name):
    h.client().post("/configs/delete", data={"configs": json.dumps([{"name": name, "type": "http"}])})

    h.db.delete_custom_configs.assert_not_called()


def test_delete_passes_a_digit_only_string_name_as_the_exact_key(h, cfg):
    h.client().post("/configs/delete", data={"configs": json.dumps([{"name": "0", "type": "http"}])})

    h.db.delete_custom_configs.assert_called_once_with({(None, "http", "0")})
