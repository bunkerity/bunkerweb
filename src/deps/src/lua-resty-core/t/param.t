# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 1);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.arg getter in set_by_lua
--- config
    location = /t {
        # set_by_lua_block doesn't support arguments
        set_by_lua $res '
            local arg = ngx.arg
            local val
            for i = 1, 30 do
                val = arg[1] + arg[2]
            end
            return val
        ' $arg_a $arg_b;
        echo $res;
    }
--- request
GET /t?a=1&b=2
--- response_body
3
--- error_log eval
qr/\[TRACE\s+\d+ set_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI: (?!return to lower frame)



=== TEST 2: ngx.arg getter in body_filter_by_lua
--- config
    location = /t {
        echo hello;
        body_filter_by_lua_block {
            local arg = ngx.arg
            local eof
            local body = ""
            for i = 1, 30 do
                body = body .. arg[1]
                eof = arg[2]
            end
        }
    }
--- request
GET /t
--- error_log eval
qr/\[TRACE\s+\d+ body_filter_by_lua\(nginx\.conf:\d+\):5 loop\]/
--- no_error_log
[error]
 -- NYI: (?!return to lower frame)
