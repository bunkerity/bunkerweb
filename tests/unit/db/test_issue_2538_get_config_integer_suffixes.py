"""``get_config`` compared the integer suffix column with the text captured from the setting name.

Expanding the numbered settings of a service (``REVERSE_PROXY_URL_2``) looked up the matching template setting
with the suffix as the string the regex captured. SQLite coerces ``'2'`` to ``2`` and hid it; PostgreSQL rejects
the comparison of an integer column with text, and the scheduler crashed while applying the configuration of any
service that used numbered settings together with a template. The suffix is now an integer, so the lookup works
on every engine. The test needs PostgreSQL to be able to fail (``--db-engines postgresql``); on SQLite it is the
behavioural twin.

Refs: #2538.
"""

from datetime import datetime, timezone

from fixtures.seed import add_global_value, add_service_setting, seed_minimal, session
from model import Template_settings, Template_steps, Templates

SERVICE = "app1.example.com"
NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _seed(db):
    seed_minimal(db)
    add_global_value(db, setting_id="MULTISITE", value="yes")
    add_global_value(db, setting_id="SERVER_NAME", value=SERVICE)
    with session(db) as s:
        s.add(Templates(id="tpl", name="Tpl", method="manual", creation_date=NOW, last_update=NOW))
        s.flush()
        s.add(Template_steps(id=1, template_id="tpl", title="Step"))
        s.flush()
        s.add(Template_settings(template_id="tpl", setting_id="REVERSE_PROXY_URL", step_id=1, default="/from-template", suffix=1, order=1))
    add_service_setting(db, service_id=SERVICE, setting_id="USE_TEMPLATE", value="tpl")
    add_service_setting(db, service_id=SERVICE, setting_id="REVERSE_PROXY_URL", value="/own", suffix=2)


def test_numbered_settings_expand_next_to_a_template_that_numbers_them(db):
    _seed(db)

    config = db.get_config()

    assert config[f"{SERVICE}_REVERSE_PROXY_URL_1"] == "/from-template"
    assert config[f"{SERVICE}_REVERSE_PROXY_URL_2"] == "/own"
