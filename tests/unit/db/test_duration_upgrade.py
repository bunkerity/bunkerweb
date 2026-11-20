"""A database holding 1.6.16 duration values survives 1.7's ``init_tables`` and is read correctly.

1.6.16 accepts ``BAD_BEHAVIOR_BAN_TIME=2h``; the value is stored. 1.7 used to answer an upgrade by
deleting a custom template whose default was ``1d`` (``_it_validate_template_settings``) and by
declaring the stored value invalid, while the Lua reader turned the same string into a permanent
ban. Here the 1.6.16 state is built from the shipped plugin file with the setting's 1.6.16
definition, then the shipped definition is applied over it.
"""

import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from common_utils import parse_duration_int
from fixtures.seed import make_general_settings, session
from model import Global_values, Template_settings, Template_steps, Templates
from Database import Database

ROOT = Path(__file__).resolve().parents[3]
SHIPPED = ROOT / "src" / "common" / "core" / "badbehavior" / "plugin.json"

# 1.6.16: git show v1.6.16:src/common/core/badbehavior/plugin.json, the BAD_BEHAVIOR_BAN_TIME entry
BAN_TIME_1616 = {"regex": r"^\d+(ms?|[shdwMy])?$", "type": "text", "default": "1d"}


@pytest.fixture
def upgraded(tmp_path):
    log = io.StringIO()
    logger = logging.getLogger("duration-upgrade")
    logger.setLevel(logging.DEBUG)
    logger.handlers[:] = [logging.StreamHandler(log)]
    logger.propagate = False
    db = Database(logger, sqlalchemy_string=f"sqlite:///{tmp_path / 'upgrade.db'}", log=False)

    shipped = json.loads(SHIPPED.read_text())
    old = json.loads(SHIPPED.read_text())
    old["settings"]["BAD_BEHAVIOR_BAN_TIME"] |= BAN_TIME_1616

    assert db.init_tables([make_general_settings(), old])[0]
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with session(db) as s:
        s.add(Global_values(setting_id="BAD_BEHAVIOR_BAN_TIME", value="2h", method="ui", suffix=0))
        s.add(Templates(id="mytpl", name="mytpl", method="ui", creation_date=now, last_update=now))
        s.flush()
        s.add(Template_steps(id=1, template_id="mytpl", title="t"))
        s.flush()
        s.add(Template_settings(template_id="mytpl", setting_id="BAD_BEHAVIOR_BAN_TIME", step_id=1, default="1d", suffix=0, order=0))
    log.truncate(0)
    log.seek(0)
    assert db.init_tables([make_general_settings(), shipped])[0]
    yield db, log.getvalue()
    db.close()


def test_the_custom_template_default_survives(upgraded):
    db, log = upgraded
    with session(db) as s:
        rows = [(t.setting_id, t.default) for t in s.query(Template_settings).all()]
    assert rows == [("BAD_BEHAVIOR_BAN_TIME", "1d")], log
    assert "deleting it" not in log


def test_both_1616_values_are_still_valid(upgraded):
    db, _ = upgraded
    assert db.is_valid_setting("BAD_BEHAVIOR_BAN_TIME", value="2h")[0]
    assert db.is_valid_setting("BAD_BEHAVIOR_BAN_TIME", value="1d")[0]
    assert db.is_valid_setting("BAD_BEHAVIOR_BAN_TIME", value="86400")[0]
    assert not db.is_valid_setting("BAD_BEHAVIOR_BAN_TIME", value="soon")[0]


def test_the_reader_yields_the_right_seconds(upgraded):
    db, _ = upgraded
    stored = db.get_config(global_only=True)["BAD_BEHAVIOR_BAN_TIME"]
    assert stored == "2h"
    assert parse_duration_int(stored, "s") == 7200
    with session(db) as s:
        default = s.query(Template_settings).one().default
    assert parse_duration_int(default, "s") == 86400
