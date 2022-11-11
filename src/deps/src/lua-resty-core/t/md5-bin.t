# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: set md5_bin (string)
--- config
    location = /md5_bin {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5_bin("hello")
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /md5_bin
--- response_body
16
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 2: set md5_bin (nil)
--- config
    location = /md5_bin {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5_bin(nil)
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /md5_bin
--- response_body
16
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 3: set md5_bin (number)
--- config
    location = /md5_bin {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5_bin(3.14)
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /md5_bin
--- response_body
16
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 4: set md5_bin (boolean)
--- config
    location = /md5_bin {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5_bin(true)
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /md5_bin
--- response_body
16
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
