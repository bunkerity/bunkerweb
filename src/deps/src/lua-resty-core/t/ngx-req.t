use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }
});

no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx_req.add_header (jitted)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            for i = 1, $TEST_NGINX_HOTLOOP * 20 do
                ngx_req.add_header("Foo", "bar")
            end
        }
    }
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]



=== TEST 2: ngx_req.add_header (single value)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx.req.set_header("Foo", "bar")
            ngx_req.add_header("Foo", "baz")
            ngx_req.add_header("Foo", 2)

            ngx.say("Foo: ", table.concat(ngx.req.get_headers()["Foo"], ", "))
        }
    }
--- response_body
Foo: bar, baz, 2



=== TEST 3: ngx_req.add_header (empty single value)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx.req.set_header("Foo", "bar")
            ngx_req.add_header("Foo", "")

            ngx.say("Foo: [", table.concat(ngx.req.get_headers()["Foo"], ", "), ']')
        }
    }
--- response_body
Foo: [bar, ]



=== TEST 4: ngx_req.add_header (non-string single value)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx.req.set_header("Foo", "bar")
            ngx_req.add_header("Foo", 123)

            ngx.say("Foo: [", table.concat(ngx.req.get_headers()["Foo"], ", "), ']')
        }
    }
--- response_body
Foo: [bar, 123]



=== TEST 5: ngx_req.add_header (non-string header name)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx_req.add_header(123, 456)
            ngx_req.add_header(123, 789)

            ngx.say("123: [", table.concat(ngx.req.get_headers()[123], ", "), ']')
        }
    }
--- response_body
123: [456, 789]



=== TEST 6: ngx_req.add_header (multiple values)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx.req.set_header("Foo", "bar")
            ngx_req.add_header("Foo", { "baz", 123 })

            ngx.say("Foo: ", table.concat(ngx.req.get_headers()["Foo"], ", "))
        }
    }
--- response_body
Foo: bar, baz, 123



=== TEST 7: ngx_req.add_header (override builtin header)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx_req.add_header("User-Agent", "Mozilla/5.0 (Android; Mobile; rv:13.0) Gecko/13.0 Firefox/13.0")

            ngx.say("UA: ", ngx.var.http_user_agent)
        }
    }
--- response_body
UA: Mozilla/5.0 (Android; Mobile; rv:13.0) Gecko/13.0 Firefox/13.0



=== TEST 8: ngx_req.add_header (added header is inherited by subrequests)
--- config
    location = /sub {
        content_by_lua_block {
            ngx.say("Foo: ", table.concat(ngx.req.get_headers()["Foo"], ", "))
        }
    }

    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            ngx.req.set_header("Foo", "bar")
            ngx_req.add_header("Foo", {"baz", 2})

            local res = ngx.location.capture("/sub")
            ngx.print(res.body)
        }
    }
--- response_body
Foo: bar, baz, 2



=== TEST 9: ngx_req.add_header (invalid context)
--- http_config
    init_worker_by_lua_block {
        local ngx_req = require "ngx.req"

        ngx_req.add_header("Foo", "baz")
    }
--- config
    location /t {
        return 200;
    }
--- response_body
--- error_log
API disabled in the current context



=== TEST 10: ngx_req.add_header (header names edge-cases)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            local function check_invalid_header_name(header_name)
                local ok, err = pcall(ngx_req.add_header, header_name, "bar")
                if not ok then
                    ngx.say(err)
                else
                    ngx.say("ok")
                end
            end

            check_invalid_header_name()
            check_invalid_header_name("")
            check_invalid_header_name({})
        }
    }
--- response_body
bad 'name' argument: string expected, got nil
ok
ok



=== TEST 11: ngx_req.add_header (invalid header values)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_req = require "ngx.req"

            local function check_invalid_header_value(...)
                local ok, err = pcall(ngx_req.add_header, "Foo", ...)
                if not ok then
                    ngx.say(err)
                else
                    ngx.say("ok")
                end
            end

            check_invalid_header_value()
            check_invalid_header_value(nil)
            check_invalid_header_value({})
        }
    }
--- response_body
bad 'value' argument: string or table expected, got nil
bad 'value' argument: string or table expected, got nil
bad 'value' argument: non-empty table expected



=== TEST 12: ngx_req.add_header (header name with control characters)
--- config
    location /bar {
        access_by_lua_block {
            local ngx_req = require "ngx.req"
            ngx_req.add_header("header\r\nabc", "value")
        }
        proxy_pass http://127.0.0.1:$server_port/foo;
    }

    location = /foo {
        echo $echo_client_request_headers;
    }
--- request
GET /bar
--- response_body_like chomp
\bheader%0D%0Aabc: value\r\n



=== TEST 13: ngx_req.add_header (header value with control characters)
--- config
    location /bar {
        access_by_lua_block {
            local ngx_req = require "ngx.req"
            ngx_req.add_header("header", "value\r\nabc")
        }
        proxy_pass http://127.0.0.1:$server_port/foo;
    }

    location = /foo {
        echo $echo_client_request_headers;
    }
--- request
GET /bar
--- response_body_like chomp
\bheader: value%0D%0Aabc\r\n



=== TEST 14: ngx_req.add_header (header name with Chinese characters)
--- config
    location /bar {
        access_by_lua_block {
            local ngx_req = require "ngx.req"
            ngx_req.add_header("header中文", "value")
        }
        proxy_pass http://127.0.0.1:$server_port/foo;
    }

    location = /foo {
        echo $echo_client_request_headers;
    }
--- request
GET /bar
--- response_body_like chomp
\bheader%E4%B8%AD%E6%96%87: value



=== TEST 15: ngx_req.add_header (header value with Chinese characters)
--- config
    location /bar {
        access_by_lua_block {
            local ngx_req = require "ngx.req"
            ngx_req.add_header("header", "value中文")
        }
        proxy_pass http://127.0.0.1:$server_port/foo;
    }

    location = /foo {
        echo $echo_client_request_headers;
    }
--- request
GET /bar
--- response_body_like chomp
\bheader: value中文
