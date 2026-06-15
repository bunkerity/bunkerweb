"""db_methods.common.bulk_add_in_fk_order — type bucketing + FK-ordered flush.

The payoff is on PostgreSQL/MariaDB, which enforce FKs: a Settings row added before
its parent Plugins must still commit because bulk_add flushes plugins/settings first.
SQLite (FKs off) can't observe the violation but still validates the linkage.
"""

from sqlalchemy.orm import Session

from db_methods.common import bulk_add_in_fk_order  # type: ignore
from model import Plugins, Settings  # type: ignore


def test_unordered_fk_children_commit(db):
    plugin = Plugins(id="p1", name="P1", description="d", version="1.0")
    setting = Settings(id="S1", name="S1", plugin_id="p1", context="global", help="h", regex="^.*$", type="text", default="")
    with Session(db.sql_engine) as s:
        bulk_add_in_fk_order(s, [setting, plugin])  # deliberately child-before-parent
        s.commit()
    with Session(db.sql_engine) as s:
        assert s.get(Settings, "S1").plugin_id == "p1"


def test_empty_items_is_noop(db):
    with Session(db.sql_engine) as s:
        bulk_add_in_fk_order(s, [])
        s.commit()  # must not raise
