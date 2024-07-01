# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 6);

no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.req.start_time()
--- stream_server_config
    content_by_lua_block {
        local t
        for i = 1, 500 do
            t = ngx.req.start_time()
        end
        ngx.sleep(0.10)
        local elapsed = ngx.now() - t
        ngx.say(t > 1399867351)
        ngx.say(">= 0.099: ", elapsed >= 0.099)
        ngx.say("< 0.11: ", elapsed < 0.11)
        -- ngx.say(t, " ", elapsed)
    }
--- stream_response
true
>= 0.099: true
< 0.11: true

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch
