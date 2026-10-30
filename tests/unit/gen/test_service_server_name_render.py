"""A service with no ``SERVER_NAME`` row of its own renders ``server_name <its id>;``.

End to end through the scheduler's path (database -> ``get_non_default_settings`` -> ``Templator``). With a
stored global ``SERVER_NAME`` the service inherited it instead: ``server_name ;`` when it is empty (the
Linux ``variables.env`` ships ``SERVER_NAME=``), which nginx refuses for the whole configuration, and a
host the operator never gave this service otherwise (dev ``cea19bc67``).
"""

import re

import pytest

from fixtures.seed import session
from model import Global_values, Services_settings  # type: ignore

pytestmark = pytest.mark.slow

SERVICE = "app1.example.com"
OTHER = "app2.example.com"


@pytest.fixture
def render_without_the_name(db, render_db_tree, monkeypatch):
    """`render_db_tree` for two services, after dropping the first one's name row and setting the global value.

    `render_db_tree` saves `<service>_SERVER_NAME` the way the UI and the API do; the row is deleted after
    the save, which is the state of a service whose name was never stored.
    """
    save_config = db.save_config

    def render(global_server_name):
        def save_without_the_name(*args, **kwargs):
            result = save_config(*args, **kwargs)
            with session(db) as s:
                s.query(Services_settings).filter_by(service_id=SERVICE, setting_id="SERVER_NAME").delete()
                if global_server_name is not None:
                    s.query(Global_values).filter_by(setting_id="SERVER_NAME", suffix=0).update({"value": global_server_name})
            return result

        monkeypatch.setattr(db, "save_config", save_without_the_name)
        tree = render_db_tree({}, {SERVICE: {}, OTHER: {}})
        return {service: re.findall(r"^\s*server_name ([^;]*);", tree[f"{service}/server.conf"], re.MULTILINE) for service in (SERVICE, OTHER)}

    return render


@pytest.mark.parametrize("global_server_name", [None, "", "global.example.com"], ids=["roster-as-global", "linux-empty-global", "named-global"])
def test_the_service_is_served_under_its_id(render_without_the_name, global_server_name):
    """`roster-as-global` is what a save stores in multisite: the global value then lists BOTH services."""
    assert render_without_the_name(global_server_name) == {SERVICE: [SERVICE], OTHER: [OTHER]}
