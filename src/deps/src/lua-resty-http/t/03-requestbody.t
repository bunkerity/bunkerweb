use Test::Nginx::Socket 'no_plan';
use Cwd qw(cwd);

my $pwd = cwd();

$ENV{TEST_NGINX_RESOLVER} = '8.8.8.8';
$ENV{TEST_COVERAGE} ||= 0;

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;/usr/local/share/lua/5.1/?.lua;;";
    error_log logs/error.log debug;

    init_by_lua_block {
        if $ENV{TEST_COVERAGE} == 1 then
            jit.off()
            require("luacov.runner").init()
        end
    }
};

no_long_string();
#no_diff();

run_tests();

__DATA__
=== TEST 1: POST form-urlencoded
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port
            })

            local res, err = httpc:request{
                body = "a=1&b=2&c=3",
                path = "/b",
                headers = {
                    ["Content-Type"] = "application/x-www-form-urlencoded",
                }
            }

            ngx.say(res:read_body())
            httpc:close()
        ';
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            local args = ngx.req.get_post_args()
            ngx.say("a: ", args.a)
            ngx.say("b: ", args.b)
            ngx.print("c: ", args.c)
        ';
    }
--- request
GET /a
--- response_body
a: 1
b: 2
c: 3
--- no_error_log
[error]
[warn]


=== TEST 2: POST form-urlencoded 1.0
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port
            })

            local res, err = httpc:request{
                method = "POST",
                body = "a=1&b=2&c=3",
                path = "/b",
                headers = {
                    ["Content-Type"] = "application/x-www-form-urlencoded",
                },
                version = 1.0,
            }

            ngx.say(res:read_body())
            httpc:close()
        ';
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            local args = ngx.req.get_post_args()
            ngx.say(ngx.req.get_method())
            ngx.say("a: ", args.a)
            ngx.say("b: ", args.b)
            ngx.print("c: ", args.c)
        ';
    }
--- request
GET /a
--- response_body
POST
a: 1
b: 2
c: 3
--- no_error_log
[error]
[warn]


=== TEST 3: 100 Continue does not end requset
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port
            })

            local res, err = httpc:request{
                body = "a=1&b=2&c=3",
                path = "/b",
                headers = {
                    ["Expect"] = "100-continue",
                    ["Content-Type"] = "application/x-www-form-urlencoded",
                }
            }
            ngx.say(res.status)
            ngx.say(res:read_body())
            httpc:close()
        ';
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            local args = ngx.req.get_post_args()
            ngx.say("a: ", args.a)
            ngx.say("b: ", args.b)
            ngx.print("c: ", args.c)
        ';
    }
--- request
GET /a
--- response_body
200
a: 1
b: 2
c: 3
--- no_error_log
[error]
[warn]

=== TEST 4: Return non-100 status to user
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port
            })

            local res, err = httpc:request{
                path = "/b",
                headers = {
                    ["Expect"] = "100-continue",
                    ["Content-Type"] = "application/x-www-form-urlencoded",
                }
            }
            if not res then
                ngx.say(err)
            end
            ngx.say(res.status)
            ngx.say(res:read_body())
            httpc:close()
        ';
    }
    location = /b {
        return 417 "Expectation Failed";
    }
--- request
GET /a
--- response_body
417
Expectation Failed
--- no_error_log
[error]
[warn]


=== TEST 5: Non string request bodies are converted with correct length
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local httpc = require("resty.http").new()

            local uri = "http://127.0.0.1:" .. ngx.var.server_port .. "/b"

            for _, body in ipairs({ 12345,
                                    true,
                                    "string",
                                    { "tab", "le" },
                                    { "mix", 123, "ed", "tab", "le" } }) do

                local res, err = assert(httpc:request_uri(uri, {
                    body = body,
                }))

                ngx.say(res.body)
            end
        ';
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            ngx.print(ngx.req.get_body_data())
        ';
    }
--- request
GET /a
--- response_body
12345
true
string
table
mix123edtable
--- no_error_log
[error]
[warn]


=== TEST 6: Request body as iterator
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local httpc = require("resty.http").new()

            local uri = "http://127.0.0.1:" .. ngx.var.server_port .. "/b"

            local res, err = assert(httpc:request_uri(uri, {
                body = coroutine.wrap(function()
                    coroutine.yield("foo")
                    coroutine.yield("bar")
                end),
                headers = {
                    ["Content-Length"] = 6
                }
            }))

            ngx.say(res.body)
        ';
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            ngx.print(ngx.req.get_body_data())
        ';
    }
--- request
GET /a
--- response_body
foobar
--- no_error_log
[error]
[warn]


=== TEST 7: Request body as iterator, errors with missing length
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local httpc = require("resty.http").new()

            local uri = "http://127.0.0.1:" .. ngx.var.server_port .. "/b"

            local res, err = httpc:request_uri(uri, {
                body = coroutine.wrap(function()
                    coroutine.yield("foo")
                    coroutine.yield("bar")
                end),
            })

            assert(not res)
            ngx.say(err)
        ';
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            ngx.print(ngx.req.get_body_data())
        ';
    }
--- request
GET /a
--- response_body
Request body is a function but a length or chunked encoding is not specified
--- no_error_log
[error]
[warn]


=== TEST 8: Request body as iterator with chunked encoding
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua_block {
            local httpc = require("resty.http").new()
            local yield = coroutine.yield

            local uri = "http://127.0.0.1:" .. ngx.var.server_port .. "/b"

            local res, err = assert(httpc:request_uri(uri, {
                body = coroutine.wrap(function()
                    yield("3\r\n")
                    yield("foo\r\n")

                    yield("3\r\n")
                    yield("bar\r\n")

                    yield("0\r\n")
                    yield("\r\n")
                end),
                headers = {
                    ["Transfer-Encoding"] = "chunked"
                }
            }))

            ngx.say(res.body)
        }
    }
    location = /b {
        content_by_lua '
            ngx.req.read_body()
            ngx.print(ngx.req.get_body_data())
        ';
    }
--- request
GET /a
--- response_body
foobar
--- no_error_log
[error]
[warn]
