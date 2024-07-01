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
=== TEST 1: Simple URI interface
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri("http://127.0.0.1:"..ngx.var.server_port.."/b?a=1&b=2")

            if not res then
                ngx.log(ngx.ERR, err)
            end
            ngx.status = res.status

            ngx.header["X-Header-A"] = res.headers["X-Header-A"]
            ngx.header["X-Header-B"] = res.headers["X-Header-B"]

            ngx.print(res.body)
        ';
    }
    location = /b {
        content_by_lua '
            for k,v in pairs(ngx.req.get_uri_args()) do
                ngx.header["X-Header-" .. string.upper(k)] = v
            end
            ngx.say("OK")
        ';
    }
--- request
GET /a
--- response_headers
X-Header-A: 1
X-Header-B: 2
--- response_body
OK
--- no_error_log
[error]
[warn]


=== TEST 2: Simple URI interface HTTP 1.0
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri(
                "http://127.0.0.1:"..ngx.var.server_port.."/b?a=1&b=2", {
                }
            )

            ngx.status = res.status

            ngx.header["X-Header-A"] = res.headers["X-Header-A"]
            ngx.header["X-Header-B"] = res.headers["X-Header-B"]

            ngx.print(res.body)
        ';
    }
    location = /b {
        content_by_lua '
            for k,v in pairs(ngx.req.get_uri_args()) do
                ngx.header["X-Header-" .. string.upper(k)] = v
            end
            ngx.say("OK")
        ';
    }
--- request
GET /a
--- response_headers
X-Header-A: 1
X-Header-B: 2
--- response_body
OK
--- no_error_log
[error]
[warn]


=== TEST 3 Simple URI interface, params override
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri(
                "http://127.0.0.1:"..ngx.var.server_port.."/b?a=1&b=2", {
                    path = "/c",
                    query = {
                        a = 2,
                        b = 3,
                    },
                }
            )

            ngx.status = res.status

            ngx.header["X-Header-A"] = res.headers["X-Header-A"]
            ngx.header["X-Header-B"] = res.headers["X-Header-B"]

            ngx.print(res.body)
        ';
    }
    location = /c {
        content_by_lua '
            for k,v in pairs(ngx.req.get_uri_args()) do
                ngx.header["X-Header-" .. string.upper(k)] = v
            end
            ngx.say("OK")
        ';
    }
--- request
GET /a
--- response_headers
X-Header-A: 2
X-Header-B: 3
--- response_body
OK
--- no_error_log
[error]
[warn]


=== TEST 4 Simple URI interface, params override, query as string
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri(
                "http://127.0.0.1:"..ngx.var.server_port.."/b?a=1&b=2", {
                    path = "/c",
                    query = "a=2&b=3",
                }
            )

            ngx.status = res.status

            ngx.header["X-Header-A"] = res.headers["X-Header-A"]
            ngx.header["X-Header-B"] = res.headers["X-Header-B"]

            ngx.print(res.body)
        ';
    }
    location = /c {
        content_by_lua '
            for k,v in pairs(ngx.req.get_uri_args()) do
                ngx.header["X-Header-" .. string.upper(k)] = v
            end
            ngx.say("OK")
        ';
    }
--- request
GET /a
--- response_headers
X-Header-A: 2
X-Header-B: 3
--- response_body
OK
--- no_error_log
[error]
[warn]


=== TEST 5 Simple URI interface, params override, query as string, as leading ?
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri(
                "http://127.0.0.1:"..ngx.var.server_port.."/b?a=1&b=2", {
                    query = "?a=2&b=3",
                }
            )

            ngx.status = res.status

            ngx.header["X-Header-A"] = res.headers["X-Header-A"]
            ngx.header["X-Header-B"] = res.headers["X-Header-B"]

            ngx.print(res.body)
        ';
    }
    location = /b {
        content_by_lua '
            for k,v in pairs(ngx.req.get_uri_args()) do
                ngx.header["X-Header-" .. string.upper(k)] = v
            end
            ngx.say("OK")
        ';
    }
--- request
GET /a
--- response_headers
X-Header-A: 2
X-Header-B: 3
--- response_body
OK
--- no_error_log
[error]
[warn]

=== TEST 6: Connection is closed on error
--- http_config eval: $::HttpConfig
--- config
    lua_socket_read_timeout 100ms;
    location = /a {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri("http://127.0.0.1:"..ngx.var.server_port.."/b?a=1&b=2")

            if not res then
                ngx.log(ngx.ERR, err)
            else
                return ngx.say("BAD")
            end

            local ok, err = httpc.sock:close()
            ngx.say(ok, " ", err)

        }
    }
    location = /b {
        content_by_lua_block {
            ngx.say("1")
            ngx.flush(true)
            ngx.sleep(0.5)
            ngx.say("2")

        }
    }
--- request
GET /a
--- response_body
nil closed
--- error_log
lua tcp socket read timed out


=== TEST 7: Content-Length is set on POST/PUT/PATCH requests when body is absent
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            for i, method in ipairs({ "POST", "PUT", "PATCH" }) do
              local http = require "resty.http"
              local httpc = http.new()
              local res, err = httpc:request_uri("http://127.0.0.1:"..ngx.var.server_port.."/b", { method = method })

              if not res then
                  ngx.log(ngx.ERR, err)
              end

              if i == 1 then
                ngx.status = res.status
              end

              ngx.print(res.body)
            end
        ';
    }
    location = /b {
        content_by_lua '
            ngx.say(ngx.req.get_method(), " Content-Length: ", ngx.req.get_headers()["Content-Length"])
        ';
    }
--- request
GET /a
--- response_body
POST Content-Length: 0
PUT Content-Length: 0
PATCH Content-Length: 0
--- no_error_log
[error]
[warn]


=== TEST 8: Content-Length is not set on GET requests when body is absent
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local res, err = httpc:request_uri("http://127.0.0.1:"..ngx.var.server_port.."/b")

            if not res then
                ngx.log(ngx.ERR, err)
            end
            ngx.status = res.status
            ngx.print(res.body)
        ';
    }
    location = /b {
        content_by_lua '
            ngx.say("Content-Length: ", type(ngx.req.get_headers()["Content-Length"]))
        ';
    }
--- request
GET /a
--- response_body
Content-Length: nil
--- no_error_log
[error]
[warn]

