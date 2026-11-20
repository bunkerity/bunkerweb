"""Behaviour of ``src/bw/lua/bunkerweb/logger.lua``, the real file run under plain Lua.

The logger is the prefix every plugin puts in front of its messages. Level filtering is not its job
(``ngx.errlog.raw_log`` does it), so the contract is: the level goes through untouched and the message is
written as ``[PREFIX] msg`` with the prefix upper-cased. ``middleclass`` is the real file; only
``ngx.errlog`` is a stand-in that records what it is asked to write.
"""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("LOGGER", BW_MODULES / "logger.lua")


def run(body):
    return run_core(MODULE, "local logger = dofile(MODULE)\n" + body)


class TestPrefix:
    def test_the_prefix_is_upper_cased_and_bracketed(self):
        assert run('logger:new("antibot"):log(ngx.ERR, "boom") emit(LOGS)') == [["ERR", "[ANTIBOT] boom"]]

    def test_mixed_case_digits_and_underscores_are_kept_apart_from_the_case_change(self):
        assert run('logger:new("Bad_Behavior2"):log(ngx.WARN, "x") emit(LOGS)') == [["WARN", "[BAD_BEHAVIOR2] x"]]

    def test_each_instance_keeps_its_own_prefix(self):
        out = run("""
local a, b = logger:new("one"), logger:new("two")
a:log(ngx.INFO, "first")
b:log(ngx.INFO, "second")
a:log(ngx.INFO, "third")
emit(LOGS)
""")
        assert out == [["INFO", "[ONE] first"], ["INFO", "[TWO] second"], ["INFO", "[ONE] third"]]

    def test_building_another_instance_does_not_change_an_existing_prefix(self):
        assert run('local l = logger:new("core") l:log(ngx.ERR, "a") logger:new("other") l:log(ngx.ERR, "b") emit(LOGS)') == [
            ["ERR", "[CORE] a"],
            ["ERR", "[CORE] b"],
        ]


class TestLevelAndMessage:
    @pytest.mark.parametrize("level", ["ERR", "WARN", "INFO", "NOTICE"])
    def test_the_level_reaches_raw_log_unchanged(self, level):
        assert run(f'logger:new("x"):log(ngx.{level}, "m") emit(LOGS)') == [[level, "[X] m"]]

    def test_no_message_is_dropped_by_the_logger_itself(self):
        out = run("""
local l = logger:new("x")
for _, level in ipairs({ ngx.INFO, ngx.NOTICE, ngx.WARN, ngx.ERR }) do l:log(level, "m") end
emit(#LOGS)
""")
        assert out == 4

    def test_the_message_is_written_verbatim_after_the_prefix(self):
        assert run('logger:new("x"):log(ngx.ERR, "a [b] %d \\n c") emit(LOGS)') == [["ERR", "[X] a [b] %d \n c"]]

    def test_an_empty_message_still_carries_the_prefix(self):
        assert run('logger:new("x"):log(ngx.ERR, "") emit(LOGS)') == [["ERR", "[X] "]]

    def test_a_number_message_is_concatenated(self):
        assert run('logger:new("x"):log(ngx.ERR, 42) emit(LOGS)') == [["ERR", "[X] 42"]]
