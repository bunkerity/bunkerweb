use Test::Nginx::Socket 'no_plan';
use Cwd qw(cwd);

my $pwd = cwd();

$ENV{TEST_NGINX_RESOLVER} = '8.8.8.8';
$ENV{TEST_NGINX_PWD} ||= $pwd;
$ENV{TEST_COVERAGE} ||= 0;

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;/usr/local/share/lua/5.1/?.lua;;";
    error_log logs/error.log debug;
    resolver 8.8.8.8;

    init_by_lua_block {
        if $ENV{TEST_COVERAGE} == 1 then
            jit.off()
            require("luacov.runner").init()
        end
    }
};

no_long_string();
run_tests();

__DATA__

=== TEST 1: get_proxy_uri returns nil if proxy is not configured
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            ngx.say(httpc:get_proxy_uri("http", "example.com"))
        }
    }
--- request
GET /lua
--- response_body
nil
--- no_error_log
[error]
[warn]



=== TEST 2: get_proxy_uri matches no_proxy hosts correctly
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()

            -- helper that verifies get_proxy_uri works correctly with the given
            -- scheme, host and no_proxy list
            local function test_no_proxy(scheme, host, no_proxy)
                httpc:set_proxy_options({
                    http_proxy = "http://http_proxy.example.com",
                    https_proxy = "http://https_proxy.example.com",
                    no_proxy = no_proxy
                })

                local proxy_uri = httpc:get_proxy_uri(scheme, host)
                ngx.say("scheme: ", scheme, ", host: ", host, ", no_proxy: ", no_proxy, ", proxy_uri: ", proxy_uri)
            end

            -- All these match the no_proxy list
            test_no_proxy("http", "example.com", nil)
            test_no_proxy("http", "example.com", "*")
            test_no_proxy("http", "example.com", "example.com")
            test_no_proxy("http", "sub.example.com", "example.com")
            test_no_proxy("http", "example.com", "example.com,example.org")
            test_no_proxy("http", "example.com", "example.org,example.com")

            -- Same for https for good measure
            test_no_proxy("https", "example.com", nil)
            test_no_proxy("https", "example.com", "*")
            test_no_proxy("https", "example.com", "example.com")
            test_no_proxy("https", "sub.example.com", "example.com")
            test_no_proxy("https", "example.com", "example.com,example.org")
            test_no_proxy("https", "example.com", "example.org,example.com")

            -- Edge cases

            -- example.com should match .example.com in the no_proxy list (legacy behavior of wget)
            test_no_proxy("http", "example.com", ".example.com")

            -- notexample.com should not match example.com in the no_proxy list (not a subdomain)
            test_no_proxy("http", "notexample.com", "example.com")
         }
    }
--- request
GET /lua
--- response_body
scheme: http, host: example.com, no_proxy: nil, proxy_uri: http://http_proxy.example.com
scheme: http, host: example.com, no_proxy: *, proxy_uri: nil
scheme: http, host: example.com, no_proxy: example.com, proxy_uri: nil
scheme: http, host: sub.example.com, no_proxy: example.com, proxy_uri: nil
scheme: http, host: example.com, no_proxy: example.com,example.org, proxy_uri: nil
scheme: http, host: example.com, no_proxy: example.org,example.com, proxy_uri: nil
scheme: https, host: example.com, no_proxy: nil, proxy_uri: http://https_proxy.example.com
scheme: https, host: example.com, no_proxy: *, proxy_uri: nil
scheme: https, host: example.com, no_proxy: example.com, proxy_uri: nil
scheme: https, host: sub.example.com, no_proxy: example.com, proxy_uri: nil
scheme: https, host: example.com, no_proxy: example.com,example.org, proxy_uri: nil
scheme: https, host: example.com, no_proxy: example.org,example.com, proxy_uri: nil
scheme: http, host: example.com, no_proxy: .example.com, proxy_uri: nil
scheme: http, host: notexample.com, no_proxy: example.com, proxy_uri: http://http_proxy.example.com
--- no_error_log
[error]
[warn]



=== TEST 3: get_proxy_uri returns correct proxy URIs for http and https URIs
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()

            -- helper that configures the proxy opts as proived and checks what
            -- get_proxy_uri says for the given scheme / host pair
            local function test_get_proxy_uri(scheme, host, http_proxy, https_proxy)
                httpc:set_proxy_options({
                    http_proxy = http_proxy,
                    https_proxy = https_proxy
                })

                local proxy_uri = httpc:get_proxy_uri(scheme, host)
                ngx.say(
                    "scheme: ", scheme,
                    ", host: ", host,
                    ", http_proxy: ", http_proxy,
                    ", https_proxy: ", https_proxy,
                    ", proxy_uri: ", proxy_uri
                )
            end

            -- http
            test_get_proxy_uri("http", "example.com", "http_proxy", "https_proxy")
            test_get_proxy_uri("http", "example.com", nil, "https_proxy")

            -- https
            test_get_proxy_uri("https", "example.com", "http_proxy", "https_proxy")
            test_get_proxy_uri("https", "example.com", "http_proxy", nil)
        }
    }
--- request
GET /lua
--- response_body
scheme: http, host: example.com, http_proxy: http_proxy, https_proxy: https_proxy, proxy_uri: http_proxy
scheme: http, host: example.com, http_proxy: nil, https_proxy: https_proxy, proxy_uri: nil
scheme: https, host: example.com, http_proxy: http_proxy, https_proxy: https_proxy, proxy_uri: https_proxy
scheme: https, host: example.com, http_proxy: http_proxy, https_proxy: nil, proxy_uri: nil
--- no_error_log
[error]
[warn]



=== TEST 4: request_uri uses http_proxy correctly for non-standard destination ports
--- http_config
    lua_package_path "$TEST_NGINX_PWD/lib/?.lua;;";
    error_log logs/error.log debug;
    resolver 8.8.8.8;
    server {
        listen *:8080;

        location / {
            content_by_lua_block {
                ngx.print(ngx.req.raw_header())
            }
        }
    }
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:8080",
                https_proxy = "http://127.0.0.1:8080"
            })

            -- request should go to the proxy server
            local res, err = httpc:request_uri("http://127.0.0.1:1234/target?a=1&b=2")

            if not res then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.status = res.status
            ngx.say(res.body)
        }
    }
--- request
GET /lua
--- response_body_like
^GET http://127.0.0.1:1234/target\?a=1&b=2 HTTP/.+\r\nHost: 127.0.0.1:1234.+
--- no_error_log
[error]
[warn]



=== TEST 5: request_uri uses http_proxy correctly for standard destination port
--- http_config
    lua_package_path "$TEST_NGINX_PWD/lib/?.lua;;";
    error_log logs/error.log debug;
    resolver 8.8.8.8;
    server {
        listen *:8080;

        location / {
            content_by_lua_block {
                ngx.print(ngx.req.raw_header())
            }
        }
    }
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:8080",
                https_proxy = "http://127.0.0.1:8080"
            })

            -- request should go to the proxy server
            local res, err = httpc:request_uri("http://127.0.0.1/target?a=1&b=2")

            if not res then
                ngx.log(ngx.ERR, err)
                return
            end

            -- the proxy echoed the raw request header and we shall pass it onwards
            -- to the test harness
            ngx.status = res.status
            ngx.say(res.body)
        }
    }
--- request
GET /lua
--- response_body_like
^GET http://127.0.0.1/target\?a=1&b=2 HTTP/.+\r\nHost: 127.0.0.1.+
--- no_error_log
[error]
[warn]



=== TEST 6: request_uri makes a proper CONNECT request when proxying https resources
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:12345",
                https_proxy = "http://127.0.0.1:12345"
            })

            -- Slight Hack: temporarily change the module global user agent to make it
            -- predictable for this test case
            local ua = http._USER_AGENT
            http._USER_AGENT = "test_ua"
            local res, err = httpc:request_uri("https://127.0.0.1/target?a=1&b=2")
            http._USER_AGENT = ua

            if not err then
                -- The proxy request should fail as the TCP server listening returns
                -- 403 response. We cannot really test the success case here as that
                -- would require an actual reverse proxy to be implemented through
                -- the limited functionality we have available in the raw TCP sockets
                ngx.log(ngx.ERR, "unexpected success")
                return
            end

            ngx.status = 403
            ngx.say(err)
        }
    }
--- tcp_listen: 12345
--- tcp_query eval
qr/CONNECT 127.0.0.1:443 HTTP\/1.1\r\n.*Host: 127.0.0.1:443\r\n.*/s

# The reply cannot be successful or otherwise the client would start
# to do a TLS handshake with the proxied host and that we cannot
# do with these sockets
--- tcp_reply
HTTP/1.1 403 Forbidden
Connection: close

--- request
GET /lua
--- error_code: 403
--- no_error_log
[error]
[warn]



=== TEST 7: request_uri uses http_proxy_authorization option
--- http_config
    lua_package_path "$TEST_NGINX_PWD/lib/?.lua;;";
    error_log logs/error.log debug;
    resolver 8.8.8.8;
    server {
        listen *:8080;

        location / {
            content_by_lua_block {
                ngx.print(ngx.var.http_proxy_authorization or "no-header")
            }
        }
    }
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:8080",
                http_proxy_authorization = "Basic ZGVtbzp0ZXN0",
                https_proxy = "http://127.0.0.1:8080",
                https_proxy_authorization = "Basic ZGVtbzpwYXNz"
            })

            -- request should go to the proxy server
            local res, err = httpc:request_uri("http://127.0.0.1/")
            if not res then
                ngx.log(ngx.ERR, err)
                return
            end

            -- the proxy echoed the proxy authorization header
            -- to the test harness
            ngx.status = res.status
            ngx.say(res.body)
        }
    }
--- request
GET /lua
--- response_body
Basic ZGVtbzp0ZXN0
--- no_error_log
[error]
[warn]



=== TEST 8: request_uri uses https_proxy_authorization option
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:12345",
                http_proxy_authorization = "Basic ZGVtbzp0ZXN0",
                https_proxy = "http://127.0.0.1:12345",
                https_proxy_authorization = "Basic ZGVtbzpwYXNz"
            })

            -- Slight Hack: temporarily change the module global user agent to make it
            -- predictable for this test case
            local ua = http._USER_AGENT
            http._USER_AGENT = "test_ua"
            local res, err = httpc:request_uri("https://127.0.0.1/target?a=1&b=2")
            http._USER_AGENT = ua

            if not err then
                -- The proxy request should fail as the TCP server listening returns
                -- 403 response. We cannot really test the success case here as that
                -- would require an actual reverse proxy to be implemented through
                -- the limited functionality we have available in the raw TCP sockets
                ngx.log(ngx.ERR, "unexpected success")
                return
            end

            ngx.status = 403
            ngx.say(err)
        }
    }
--- tcp_listen: 12345
--- tcp_query eval
qr/CONNECT 127.0.0.1:443 HTTP\/1.1\r\n.*Proxy-Authorization: Basic ZGVtbzpwYXNz\r\n.*/s

# The reply cannot be successful or otherwise the client would start
# to do a TLS handshake with the proxied host and that we cannot
# do with these sockets
--- tcp_reply
HTTP/1.1 403 Forbidden
Connection: close

--- request
GET /lua
--- error_code: 403
--- no_error_log
[error]
[warn]



=== TEST 9: request_uri does not use http_proxy_authorization option when overridden
--- http_config
    lua_package_path "$TEST_NGINX_PWD/lib/?.lua;;";
    error_log logs/error.log debug;
    resolver 8.8.8.8;
    server {
        listen *:8080;

        location / {
            content_by_lua_block {
                ngx.print(ngx.var.http_proxy_authorization or "no-header")
            }
        }
    }
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:8080",
                http_proxy_authorization = "Basic ZGVtbzp0ZXN0",
                https_proxy = "http://127.0.0.1:8080",
                https_proxy_authorization = "Basic ZGVtbzpwYXNz"
            })

            -- request should go to the proxy server
            local res, err = httpc:request_uri("http://127.0.0.1/", {
                headers = {
                    ["Proxy-Authorization"] = "Basic ZGVtbzp3b3Jk"
                }
            })
            if not res then
                ngx.log(ngx.ERR, err)
                return
            end

            -- the proxy echoed the proxy authorization header
            -- to the test harness
            ngx.status = res.status
            ngx.say(res.body)
        }
    }
--- request
GET /lua
--- response_body
Basic ZGVtbzp3b3Jk
--- no_error_log
[error]
[warn]



=== TEST 10: request_uri does not use https_proxy_authorization option when overridden
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            httpc:set_proxy_options({
                http_proxy = "http://127.0.0.1:12345",
                http_proxy_authorization = "Basic ZGVtbzp0ZXN0",
                https_proxy = "http://127.0.0.1:12345",
                https_proxy_authorization = "Basic ZGVtbzpwYXNz"
            })

            -- Slight Hack: temporarily change the module global user agent to make it
            -- predictable for this test case
            local ua = http._USER_AGENT
            http._USER_AGENT = "test_ua"
            local res, err = httpc:request_uri("https://127.0.0.1/target?a=1&b=2", {
                headers = {
                    ["Proxy-Authorization"] = "Basic ZGVtbzp3b3Jk"
                }
            })
            http._USER_AGENT = ua

            if not err then
                -- The proxy request should fail as the TCP server listening returns
                -- 403 response. We cannot really test the success case here as that
                -- would require an actual reverse proxy to be implemented through
                -- the limited functionality we have available in the raw TCP sockets
                ngx.log(ngx.ERR, "unexpected success")
                return
            end

            ngx.status = 403
            ngx.say(err)
        }
    }
--- tcp_listen: 12345
--- tcp_query eval
qr/CONNECT 127.0.0.1:443 HTTP\/1.1\r\n.*Proxy-Authorization: Basic ZGVtbzp3b3Jk\r\n.*/s

# The reply cannot be successful or otherwise the client would start
# to do a TLS handshake with the proxied host and that we cannot
# do with these sockets
--- tcp_reply
HTTP/1.1 403 Forbidden
Connection: close

--- request
GET /lua
--- error_code: 403
--- no_error_log
[error]
[warn]
