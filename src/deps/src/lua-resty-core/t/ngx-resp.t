use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 4);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }
});

check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.resp.add_header (single value)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header("Foo", "bar")
            ngx_resp.add_header("Foo", 2)
            ngx.say("Foo: ", table.concat(ngx.header["Foo"], ", "))
        }
    }
--- response_body
Foo: bar, 2



=== TEST 2: ngx.resp.add_header (nil)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            local ok, err = pcall(ngx_resp.add_header, "Foo")
            if not ok then
                ngx.say(err)
            else
                ngx.say('ok')
            end
        }
    }
--- response_body
invalid header value



=== TEST 3: ngx.resp.add_header (multi-value)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header('Foo', {'bar', 'baz'})
            local v = ngx.header["Foo"]
            ngx.say("Foo: ", table.concat(ngx.header["Foo"], ", "))
        }
    }
--- response_body
Foo: bar, baz



=== TEST 4: ngx.resp.add_header (append header)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx.header["fruit"] = "apple"
            ngx_resp.add_header("fruit", "banana")
            ngx_resp.add_header("fruit", "cherry")
            ngx.say("fruit: ", table.concat(ngx.header["fruit"], ", "))
        }
    }
--- response_body
fruit: apple, banana, cherry



=== TEST 5: ngx.resp.add_header (override builtin header)
--- config
    location = /t {
        set $foo hello;
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header("Date", "now")
            ngx.say("Date: ", ngx.header["Date"])
        }
    }
--- response_body
Date: now



=== TEST 6: ngx.resp.add_header (empty table)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx.header["Foo"] = "aaa"
            local ok, err = pcall(ngx_resp.add_header, "Foo", {})
            if not ok then
                ngx.say(err)
            else
                ngx.say("Foo: ", ngx.header["Foo"])
            end
        }
    }
--- response_body
Foo: aaa



=== TEST 7: ngx.resp.add_header (header name with control characters)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header("head\r\n", "value")
            ngx.say("OK")
        }
    }
--- response_body
OK
--- response_headers
head%0D%0A: value



=== TEST 8: ngx.resp.add_header (header value with control characters)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header("head", "value\r\n")
            ngx.say("OK")
        }
    }
--- response_body
OK
--- response_headers
head: value%0D%0A



=== TEST 9: ngx.resp.add_header (header name with Chinese characters)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header("head中文", "value")
            ngx.say("OK")
        }
    }
--- response_body
OK
--- response_headers
head%E4%B8%AD%E6%96%87: value



=== TEST 10: ngx.resp.add_header (header value with Chinese characters)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_resp = require "ngx.resp"
            ngx_resp.add_header("head", "value中文")
            ngx.say("OK")
        }
    }
--- response_body
OK
--- response_headers
head: value中文
