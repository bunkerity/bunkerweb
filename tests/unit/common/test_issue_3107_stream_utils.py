"""Stream services need their own deny status and their bans must be removed from every datastore.

Stream security plugins read the deny status through ``utils.get_deny_status``; it returned ``ngx.HTTP_CLOSED``, a field
that does not exist, so every stream decision carried a nil status. Removing a ban only touched the local datastore, so a
ban written by the other subsystem survived an unban. This test runs the real ``utils.lua`` in the stream subsystem.
Refs: #3107, #2516.
"""

import pytest
from _t2_helpers import LUA, run_script, utils_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def test_stream_deny_status_is_the_connection_close_code():
    out = run_script(utils_script("NEXT_SESSION = function() end\nemit({ status = utils.get_deny_status() or 'nil' })", subsystem="stream"))
    assert out["status"] == 444


def test_http_deny_status_still_comes_from_the_setting():
    body = 'VARIABLES = { global = { DENY_HTTP_STATUS = "429" } }\nemit({ status = utils.get_deny_status() })'
    assert run_script(utils_script(body, subsystem="http"))["status"] == 429


@pytest.mark.parametrize("subsystem, other", [("stream", "datastore"), ("http", "datastore_stream")])
def test_unban_clears_the_ban_written_in_the_other_subsystem_datastore(subsystem, other):
    body = f"""
VARIABLES = {{ global = {{ USE_REDIS = "no" }} }}
SHARED.{other}.data["bans_ip_1.2.3.4"] = "global-ban"
SHARED.{other}.data["bans_service_app.example.com_ip_1.2.3.4"] = "service-ban"
local ok, msg = utils.remove_ban("1.2.3.4")
emit({{ ok = ok, msg = msg, left = SHARED.{other}:get_keys() }})
"""
    # the ``datastore`` dict of the running subsystem is declared first, the other one is what the cross-subsystem path reaches
    out = run_script(utils_script(body, subsystem=subsystem))
    assert out["ok"] is True
    assert out["left"] == []
