# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 19);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.req.get_headers
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ffi = require "ffi"
            local headers
            for i = 1, 500 do
                headers = ngx.req.get_headers()
            end
            local keys = {}
            for k, _ in pairs(headers) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                ngx.say(k, ": ", headers[k])
            end
        }
    }
--- request
GET /t
--- response_body
bar: bar
baz: baz
connection: close
foo: foo
host: localhost
--- more_headers
Foo: foo
Bar: bar
Baz: baz
--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ .*? -> \d+\]/
--- no_error_log eval
[
"[error]",
qr/ -- NYI: (?!return to lower frame)/,
]



=== TEST 2: ngx.req.get_headers (raw)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ffi = require "ffi"
            local headers
            for i = 1, 500 do
                headers = ngx.req.get_headers(100, true)
            end
            local keys = {}
            for k, _ in pairs(headers) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                ngx.say(k, ": ", headers[k])
            end
        }
    }
--- request
GET /t
--- response_body
Bar: bar
Baz: baz
Connection: close
Foo: foo
Host: localhost
--- more_headers
Foo: foo
Bar: bar
Baz: baz
--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ .*? -> \d+\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 3: ngx.req.get_headers (count is 2)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ffi = require "ffi"
            local headers
            for i = 1, 500 do
                headers = ngx.req.get_headers(2, true)
            end
            local keys = {}
            for k, _ in pairs(headers) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                ngx.say(k, ": ", headers[k])
            end
        }
    }
--- request
GET /t
--- response_body
Connection: close
Host: localhost
--- more_headers
Foo: foo
Bar: bar
Baz: baz
--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 4: ngx.req.get_headers (metatable)
--- http_config eval
"
$::HttpConfig
underscores_in_headers on;
"
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ffi = require "ffi"
            local headers, header
            for i = 1, 500 do
                headers = ngx.req.get_headers()
                header = headers["foo_BAR"]
            end
            ngx.say("foo_BAR: ", header)
            local keys = {}
            for k, _ in pairs(headers) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                ngx.say(k, ": ", headers[k])
            end

            ngx.say("X_Bar_Header: ", headers["X_Bar_Header"])
            ngx.say("x_Bar_Header: ", headers["x_Bar_Header"])
            ngx.say("x_bar_header: ", headers["x_bar_header"])
        }
    }
--- request
GET /t
--- response_body
foo_BAR: foo
baz: baz
connection: close
foo-bar: foo
host: localhost
x_bar_header: bar
X_Bar_Header: bar
x_Bar_Header: bar
x_bar_header: bar
--- more_headers
Foo-Bar: foo
Baz: baz
X_Bar_Header: bar
--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ .*? -> \d+\]/
--- no_error_log eval
["[error]",
qr/ -- NYI: (?!return to lower frame at)(?!C function 0x[0-9a-f]+ at content_by_lua\(nginx.conf:\d+\):15)/,
]



=== TEST 5: ngx.req.get_uri_args
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ffi = require "ffi"
            local args
            for i = 1, 500 do
                args = ngx.req.get_uri_args()
            end
            if type(args) ~= "table" then
                ngx.say("bad args type found: ", args)
                return
            end
            local keys = {}
            for k, _ in pairs(args) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                local v = args[k]
                if type(v) == "table" then
                    ngx.say(k, ": ", table.concat(v, ", "))
                else
                    ngx.say(k, ": ", v)
                end
            end
        }
    }
--- request
GET /t?a=3%200&foo%20bar=&a=hello&blah
--- response_body
a: 3 0, hello
blah: true
foo bar: 
--- error_log eval
qr/\[TRACE\s+\d+ .*? -> \d+\]/
--- no_error_log
[error]
 -- NYI:
--- wait: 0.2



=== TEST 6: ngx.req.get_uri_args (empty)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ffi = require "ffi"
            local args
            for i = 1, 500 do
                args = ngx.req.get_uri_args()
            end
            if type(args) ~= "table" then
                ngx.say("bad args type found: ", args)
                return
            end
            local keys = {}
            for k, _ in pairs(args) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                local v = args[k]
                if type(v) == "table" then
                    ngx.say(k, ": ", table.concat(v, ", "))
                else
                    ngx.say(k, ": ", v)
                end
            end
        }
    }
--- request
GET /t?
--- response_body
--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 7: ngx.req.start_time()
--- config
    location = /t {
        access_log off;
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
    }
--- request
GET /t
--- response_body
true
>= 0.099: true
< 0.11: true

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 8: ngx.req.get_method (GET)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                t = ngx.req.get_method()
            end
            ngx.say("method: ", t)
        }
    }
--- request
GET /t
--- response_body
method: GET

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 9: ngx.req.get_method (OPTIONS)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                t = ngx.req.get_method()
            end
            ngx.say("method: ", t)
        }
    }
--- request
OPTIONS /t
--- response_body
method: OPTIONS

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 10: ngx.req.get_method (POST)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                t = ngx.req.get_method()
            end
            ngx.say("method: ", t)
            ngx.req.discard_body()
        }
    }
--- request
POST /t
hello
--- response_body
method: POST

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 11: ngx.req.get_method (unknown method)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                t = ngx.req.get_method()
            end
            ngx.say("method: ", t)
            ngx.req.discard_body()
        }
    }
--- request
BLAH /t
hello
--- response_body
method: BLAH

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 12: ngx.req.get_method (CONNECT)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                t = ngx.req.get_method()
            end
            ngx.say("method: ", t)
            ngx.req.discard_body()
        }
    }
--- request
CONNECT /t
hello
--- response_body
method: CONNECT

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch
--- skip_nginx
6: >= 1.21.1



=== TEST 13: ngx.req.set_method (GET -> PUT)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                ngx.req.set_method(ngx.HTTP_PUT)
            end
            ngx.say("method: ", ngx.req.get_method())
        }
    }
--- request
GET /t
--- response_body
method: PUT

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 14: ngx.req.set_header (single number value)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                ngx.req.set_header("foo", i)
            end
            ngx.say("header foo: ", ngx.var.http_foo)
        }
    }
--- request
GET /t
--- response_body
header foo: 500

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 15: ngx.req.set_header (nil value)
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                ngx.req.set_header("foo", nil)
            end
            ngx.say("header foo: ", type(ngx.var.http_foo))
        }
    }
--- request
GET /t
--- response_body
header foo: nil

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 16: ngx.req.clear_header
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            ngx.req.set_header("foo", "hello")
            local t
            for i = 1, 500 do
                t = ngx.req.clear_header("foo")
            end
            ngx.say("header foo: ", type(ngx.var.http_foo))
        }
    }
--- request
GET /t
--- response_body
header foo: nil

--- wait: 0.2
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 17: ngx.req.set_header (multiple values)
--- config
    location = /t {
        content_by_lua_block {
            ngx.req.set_header("Foo", { "baz", 123 })

            ngx.say("Foo: ", table.concat(ngx.req.get_headers()["Foo"], ", "))
        }
    }
--- request
GET /t
--- more_headers
Foo: bar
--- response_body
Foo: baz, 123
--- no_error_log
[error]



=== TEST 18: ngx.req.get_header (metatable is nil)
--- config
    location = /t {
        content_by_lua_block {
            local headers = ngx.req.get_headers()

            ngx.say(string.format("%s,%s",type(headers), type(getmetatable(headers))))
        }
    }

--- raw_request eval
"GET /t \r\n"
--- http09
--- response_body
table,table



=== TEST 19: CONNECT method is considered invalid since nginx 1.21.1
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 500 do
                t = ngx.req.get_method()
            end
            ngx.say("method: ", t)
            ngx.req.discard_body()
        }
    }
--- request
CONNECT /t
hello
--- error_code: 405
--- no_error_log
[error]
--- skip_nginx
2: < 1.21.1



=== TEST 20: get_uri_args allows to reuse table
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local base = require "resty.core.base"
            local args = base.new_tab(0, 3)
            local id = tostring(args)
            for i = 1, 5 do
                base.clear_tab(args)
                args = ngx.req.get_uri_args(-1, args)
                assert(tostring(args) == id)
            end
            local keys = {}
            for k, _ in pairs(args) do
                keys[#keys + 1] = k
            end
            table.sort(keys)
            for _, k in ipairs(keys) do
                local v = args[k]
                if type(v) == "table" then
                    ngx.say(k, ": ", table.concat(v, ", "))
                else
                    ngx.say(k, ": ", v)
                end
            end
        }
    }
--- request
GET /t?a=3%200&foo%20bar=&a=hello&blah
--- response_body
a: 3 0, hello
blah: true
foo bar: 
--- no_error_log
[error]



=== TEST 21: get_uri_args allows to reuse table (empty)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local base = require "resty.core.base"
            local args = base.new_tab(0, 3)
            local id = tostring(args)
            for i = 1, 5 do
                args = ngx.req.get_uri_args(-1, args)
                assert(tostring(args) == id)
            end
            local n_key = 0
            for k, _ in pairs(args) do
                n_key = n_key + 1
            end
            ngx.say(n_key)
        }
    }
--- request
GET /t
--- response_body
0
--- no_error_log
[error]
