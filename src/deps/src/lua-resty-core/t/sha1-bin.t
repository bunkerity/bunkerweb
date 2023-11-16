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

=== TEST 1: set sha1_bin (string)
--- config
    location = /sha1_bin {
        content_by_lua_block {
            local s
            for i = 1, 30 do
                s = ngx.sha1_bin("hello")
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /sha1_bin
--- response_body
20
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 2: set sha1_bin (nil)
--- config
    location = /sha1_bin {
        content_by_lua_block {
            local s
            for i = 1, 30 do
                s = ngx.sha1_bin(nil)
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /sha1_bin
--- response_body
20
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 3: set sha1_bin (number)
--- config
    location = /sha1_bin {
        content_by_lua_block {
            local s
            for i = 1, 30 do
                s = ngx.sha1_bin(3.14)
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /sha1_bin
--- response_body
20
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 4: set sha1_bin (boolean)
--- config
    location = /sha1_bin {
        content_by_lua_block {
            local s
            for i = 1, 30 do
                s = ngx.sha1_bin(true)
            end
            ngx.say(string.len(s))
        }
    }
--- request
GET /sha1_bin
--- response_body
20
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
