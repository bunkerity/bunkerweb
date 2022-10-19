# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5 + 5);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: write to ngx.header.HEADER (single value)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            for i = 1, 100 do
                ngx.header["Foo"] = i
            end
            ngx.say("Foo: ", ngx.header["Foo"])
        }
    }
--- request
GET /t
--- response_body
Foo: 100

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):2 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 2: write to ngx.header.HEADER (nil)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            for i = 1, 200 do
                ngx.header["Foo"] = i
                ngx.header["Foo"] = nil
            end
            ngx.say("Foo: ", ngx.header["Foo"])
        }
    }
--- request
GET /t
--- response_body
Foo: nil

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):2 loop\]/
--- wait: 0.2
--- no_error_log
[error]
 -- NYI:



=== TEST 3: write to ngx.header.HEADER (multi-value)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            for i = 1, 200 do
                ngx.header["Foo"] = {i, i + 1}
            end
            local v = ngx.header["Foo"]
            if type(v) == "table" then
                ngx.say("Foo: ", table.concat(v, ", "))
            else
                ngx.say("Foo: ", v)
            end
        }
    }
--- request
GET /t
--- response_body
Foo: 200, 201

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):2 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 4: read from ngx.header.HEADER (single value)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local v
            for i = 1, 100 do
                ngx.header["Foo"] = i
                v = ngx.header["Foo"]
            end
            ngx.say("Foo: ", v)
        }
    }
--- request
GET /t
--- response_body
Foo: 100

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log eval
[
"[error]",
qr/ -- NYI: (?!return to lower frame)/,
"stitch",
]



=== TEST 5: read from ngx.header.HEADER (not found)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local v
            for i = 1, 100 do
                v = ngx.header["Foo"]
            end
            ngx.say("Foo: ", v)
        }
    }
--- request
GET /t
--- response_body
Foo: nil

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:
stitch



=== TEST 6: read from ngx.header.HEADER (multi-value)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            ngx.header["Foo"] = {"foo", "bar"}
            local v
            for i = 1, 100 do
                v = ngx.header["Foo"]
            end
            ngx.say("Foo: ", table.concat(v, ", "))
        }
    }
--- request
GET /t
--- response_body
Foo: foo, bar

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:
stitch



=== TEST 7: set multi values to cache-control and override it with multiple values
--- config
    location /lua {
        content_by_lua_block {
            ngx.header.cache_control = { "private", "no-store" }
            ngx.header.cache_control = { "no-cache", "blah", "foo" }
            local v
            for i = 1, 400 do
                v = ngx.header.cache_control
            end
            ngx.say("Cache-Control: ", table.concat(v, ", "))
        }
    }
--- request
    GET /lua
--- response_headers
Cache-Control: no-cache, blah, foo
--- response_body_like chop
^Cache-Control: no-cache[;,] blah[;,] foo$
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):5 (?:loop|-> \d+)\]/
--- no_error_log
[error]
 -- NYI:
stitch
