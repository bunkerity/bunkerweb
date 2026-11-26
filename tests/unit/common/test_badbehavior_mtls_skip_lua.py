"""A4/S3: Bad Behavior does not count the failures mTLS causes unless ``MTLS_COUNT_BAD_BEHAVIOR`` is yes.

The mark is the nginx variable ``$mtls_cert_error`` (set by the plugin's 495/496 error location) or the
``mtls`` deny reason recorded by the access phase. Any other 400 on the same service counts under both values.
"""

import pytest
from _t2_helpers import requires_lua, run_plugin_script

pytestmark = requires_lua


def log(*, status=400, count=None, mark=False, reason=None, var_reason=None):
    settings = {"USE_BAD_BEHAVIOR": "yes", "BAD_BEHAVIOR_STATUS_CODES": "400 403", "BAD_BEHAVIOR_BAN_SCOPE": "service"}
    settings.update({"BAD_BEHAVIOR_BAN_TIME": "3600", "BAD_BEHAVIOR_COUNT_TIME": "60", "BAD_BEHAVIOR_THRESHOLD": "5"})
    lua_settings = ", ".join(f'{k} = "{v}"' for k, v in settings.items())
    if count is not None:
        lua_settings += f', MTLS_COUNT_BAD_BEHAVIOR = "{count}"'
    bw_reason = f', reason = "{reason}"' if reason else ""
    return run_plugin_script(
        "badbehavior",
        f"""
VARIABLES = {{ {lua_settings} }}
{'ngx.var.mtls_cert_error = "yes"' if mark else ""}
{f'ngx.var.reason = "{var_reason}"' if var_reason else ""}
local p = PLUGIN:new({{ bw = {{ remote_addr = "203.0.113.9", server_name = "app.example.com", request_uri = "/" {bw_reason} }} }})
local r = p:log()
emit({{ ret = r.ret, msg = r.msg, queued = #RPUSHES }})
""",
        header=f"STATUS = {status}\n",
    )


COUNTED = {"ret": True, "msg": "success", "queued": 1}


def skipped(out):
    return out["ret"] is True and out["queued"] == 0 and out["msg"].startswith("mTLS failure, not counted")


@pytest.mark.parametrize("count", [None, "no"])
class TestNotCounted:
    def test_a_certificate_failure_400_is_not_counted(self, count):
        assert skipped(log(count=count, mark=True))

    @pytest.mark.parametrize("status", [400, 403])
    def test_the_plugins_own_denial_is_not_counted(self, count, status):
        assert skipped(log(status=status, count=count, reason="mtls"))

    def test_the_reason_can_come_from_the_nginx_variable(self, count):
        assert skipped(log(count=count, var_reason="mtls"))


class TestCounted:
    def test_a_certificate_failure_counts_when_the_setting_is_yes(self):
        assert log(count="yes", mark=True) == COUNTED

    def test_the_plugins_own_denial_counts_when_the_setting_is_yes(self):
        assert log(status=403, count="yes", reason="mtls") == COUNTED

    @pytest.mark.parametrize("count", [None, "no", "yes"])
    def test_an_unrelated_400_counts_under_every_value(self, count):
        assert log(count=count) == COUNTED

    @pytest.mark.parametrize("count", [None, "no", "yes"])
    def test_another_plugins_denial_counts_under_every_value(self, count):
        assert log(status=403, count=count, reason="blacklist") == COUNTED

    def test_a_status_that_is_not_watched_is_left_alone_first(self):
        out = log(status=200, mark=True)
        assert out["msg"] == "not increasing counter" and out["queued"] == 0
