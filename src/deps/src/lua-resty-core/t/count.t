# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: module size
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local base = require "resty.core.base"
            local n = 0
            for _, _ in pairs(base) do
                n = n + 1
            end
            ngx.say("base size: ", n)
        }
    }
--- request
GET /re

--- stap2
global c
probe process("$LIBLUA_PATH").function("rehashtab") {
    c++
    printf("rehash: %d\n", c)
}

--- response_body
base size: 20
--- no_error_log
[error]
