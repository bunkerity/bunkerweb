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

=== TEST 1: set md5 hello
--- config
    location = /md5 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5("hello")
            end
            ngx.say(s)
        }
    }
--- request
GET /md5
--- response_body
5d41402abc4b2a76b9719d911017c592
--- error_log eval
qr/\[TRACE\s+1 content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 2: nil string to ngx.md5
--- config
    location = /md5 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5(nil)
            end
            ngx.say(s)
        }
    }
--- request
GET /md5
--- response_body
d41d8cd98f00b204e9800998ecf8427e
--- error_log eval
qr/\[TRACE\s+1 content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 3: empty string to ngx.md5
--- config
    location /md5 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5("")
            end
            ngx.say(s)
        }
    }
--- request
GET /md5
--- response_body
d41d8cd98f00b204e9800998ecf8427e
--- error_log eval
qr/\[TRACE\s+1 content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]



=== TEST 4: number to ngx.md5
--- config
    location /md5 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.md5(3.14)
            end
            ngx.say(s)
        }
    }
--- request
GET /md5
--- response_body
4beed3b9c4a886067de0e3a094246f78
--- error_log eval
qr/\[TRACE\s+1 content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
