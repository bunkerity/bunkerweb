# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

workers(5);
#worker_connections(1014);
#master_process_enabled(1);
master_on();
#log_level('warn');

repeat_each(3);

plan tests => repeat_each() * (blocks() * 6);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.worker.count
--- config
    location = /t {
        content_by_lua_block {
            local v
            local count = ngx.worker.count
            for i = 1, 30 do
                v = count()
            end
            ngx.say("workers: ", v)
        }
    }
--- request
GET /t
--- response_body
workers: 5
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:
 stitch
