"""``Database.is_valid_setting`` refuses a value with an embedded newline.

``variables.env`` is line-oriented (the scheduler writes ``KEY=VALUE\\n``), so a value carrying its
own newline would declare a second setting. The Configurator already refuses it; writers that only
reach ``is_valid_setting`` (autoconf labels and annotations, API service writes) must too. A trailing
newline stays valid (Kubernetes block scalars) and ``file`` settings keep their multi-line PEM data.
"""

import pytest

from fixtures.seed import add_setting, seed_minimal

PEM = "-----BEGIN CERTIFICATE-----\nMIIBkTCB+wIJAK==\n-----END CERTIFICATE-----"


@pytest.fixture
def loose(db):
    seed_minimal(db)
    add_setting(db, "LOOSE_TOKEN", regex=".*", type="text")
    add_setting(db, "LOOSE_CERT", regex=".*", type="file")
    return db


@pytest.mark.parametrize("value", ["value\nOTHER_SETTING=x", "value\rOTHER_SETTING=x", "a\r\nb"])
def test_embedded_newline_is_refused(loose, value):
    ok, msg = loose.is_valid_setting("LOOSE_TOKEN", value=value)

    assert ok is False
    assert "newline" in msg


def test_trailing_newline_is_accepted(loose):
    assert loose.is_valid_setting("LOOSE_TOKEN", value="value\n") == (True, "")
    assert loose.is_valid_setting("LOOSE_TOKEN", value="value\r\n") == (True, "")


def test_file_setting_keeps_multiline_value(loose):
    assert loose.is_valid_setting("LOOSE_CERT", value=PEM) == (True, "")


def test_single_line_value_is_accepted(loose):
    assert loose.is_valid_setting("LOOSE_TOKEN", value="value") == (True, "")
