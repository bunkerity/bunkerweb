# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5);

check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: get_phase
--- config
    location /lua {
        content_by_lua_block {
            local phase
            for i = 1, 100 do
                phase = ngx.get_phase()
            end
            ngx.say(phase)
        }
    }
--- request
GET /lua
--- response_body
content
--- no_error_log
[error]
 -- NYI:
--- error_log eval
qr/\[TRACE\s+\d+\s+content_by_lua\(nginx\.conf:\d+\):3 loop\]/
