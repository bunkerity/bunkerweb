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
=== TEST 1: Proxy GET request and response
--- http_config eval: $::HttpConfig
--- config
    location = /a_prx {
        rewrite ^(.*)_prx$ $1 break;
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port,
            })
            httpc:proxy_response(httpc:proxy_request())
            httpc:set_keepalive()
        ';
    }
    location = /a {
        content_by_lua '
            ngx.status = 200
            ngx.header["X-Test"] = "foo"
            ngx.say("OK")
        ';
    }
--- request
GET /a_prx
--- response_body
OK
--- response_headers
X-Test: foo
--- error_code: 200
--- no_error_log
[error]
[warn]
--- error_log
[debug]


=== TEST 2: Proxy POST request and response
--- http_config eval: $::HttpConfig
--- config
    location = /a_prx {
        rewrite ^(.*)_prx$ $1 break;
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port,
            })
            httpc:proxy_response(httpc:proxy_request())
            httpc:set_keepalive()
        ';
    }
    location = /a {
        lua_need_request_body on;
        content_by_lua '
            ngx.status = 404
            ngx.header["X-Test"] = "foo"
            local args, err = ngx.req.get_post_args()
            ngx.say(args["foo"])
            ngx.say(args["hello"])
        ';
    }
--- request
POST /a_prx
foo=bar&hello=world
--- response_body
bar
world
--- response_headers
X-Test: foo
--- error_code: 404
--- no_error_log
[error]
--- error_log
[warn]
--- error_log
[debug]


=== TEST 3: Proxy multiple headers
--- http_config eval: $::HttpConfig
--- config
    location = /a_prx {
        rewrite ^(.*)_prx$ $1 break;
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port,
            })
            httpc:proxy_response(httpc:proxy_request())
            httpc:set_keepalive()
        ';
    }
    location = /a {
        content_by_lua '
            ngx.status = 200
            ngx.header["Set-Cookie"] = { "cookie1", "cookie2" }
            ngx.say("OK")
        ';
    }
--- request
GET /a_prx
--- response_body
OK
--- raw_response_headers_like: .*Set-Cookie: cookie1\r\nSet-Cookie: cookie2\r\n
--- error_code: 200
--- no_error_log
[error]
[warn]
--- error_log
[debug]


=== TEST 4: Proxy still works with spaces in URI
--- http_config eval: $::HttpConfig
--- config
    location = "/a_ b_prx" {
        rewrite ^(.*)_prx$ $1 break;
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port,
            })
            httpc:proxy_response(httpc:proxy_request())
            httpc:set_keepalive()
        ';
    }
    location = "/a_ b" {
        content_by_lua '
            ngx.status = 200
            ngx.header["X-Test"] = "foo"
            ngx.say("OK")
        ';
    }
--- request
GET /a_%20b_prx
--- response_body
OK
--- response_headers
X-Test: foo
--- error_code: 200
--- no_error_log
[error]
[warn]
--- error_log
[debug]
