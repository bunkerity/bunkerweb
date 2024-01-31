# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

#repeat_each(120);
repeat_each(2);

plan tests => repeat_each() * (blocks() * 7);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: get ngx.status
--- config
    location = /t {
        return 201;
        header_filter_by_lua_block {
            local sum = 0
            for i = 1, 30 do
                sum = sum + ngx.status
            end
            ngx.log(ngx.WARN, "sum: ", sum)
        }
    }
--- request
GET /t
--- response_body
--- error_code: 201
--- no_error_log
[error]
 -- NYI:
 bad argument
--- error_log eval
["sum: 6030,",
qr/\[TRACE\s+\d+\s+header_filter_by_lua\(nginx.conf:\d+\):3 loop\]/
]



=== TEST 2: set ngx.status
--- config
    location = /t {
        return 201;
        header_filter_by_lua_block {
            for i = 100, 200 do
                ngx.status = i
            end
            ngx.log(ngx.WARN, "status: ", ngx.status)
        }
    }
--- request
GET /t
--- response_body
--- no_error_log
[error]
 -- NYI:
 bad argument
--- error_log eval
["status: 200,",
qr/\[TRACE\s+\d+\s+header_filter_by_lua\(nginx.conf:\d+\):2 loop\]/
]
