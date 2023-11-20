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
=== TEST 1: Parse URI errors if malformed
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require("resty.http").new()
            local parts, err = http:parse_uri("http:///example.com")
            if not parts then ngx.say(err) end
        ';
    }
--- request
GET /a
--- response_body
bad uri: http:///example.com
--- no_error_log
[error]
[warn]


=== TEST 2: Parse URI fills in defaults correctly
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require("resty.http").new()

            local function test_uri(uri)
                local scheme, host, port, path, query = unpack(http:parse_uri(uri, false))
                ngx.say("scheme: ", scheme, ", host: ", host, ", port: ", port, ", path: ", path, ", query: ", query)
            end

            test_uri("http://example.com")
            test_uri("http://example.com/")
            test_uri("https://example.com/foo/bar")
            test_uri("https://example.com/foo/bar?a=1&b=2")
            test_uri("http://example.com?a=1&b=2")
            test_uri("//example.com")
            test_uri("//example.com?a=1&b=2")
            test_uri("//example.com/foo/bar?a=1&b=2")
        ';
    }
--- request
GET /a
--- response_body
scheme: http, host: example.com, port: 80, path: /, query: 
scheme: http, host: example.com, port: 80, path: /, query: 
scheme: https, host: example.com, port: 443, path: /foo/bar, query: 
scheme: https, host: example.com, port: 443, path: /foo/bar, query: a=1&b=2
scheme: http, host: example.com, port: 80, path: /, query: a=1&b=2
scheme: http, host: example.com, port: 80, path: /, query: 
scheme: http, host: example.com, port: 80, path: /, query: a=1&b=2
scheme: http, host: example.com, port: 80, path: /foo/bar, query: a=1&b=2
--- no_error_log
[error]
[warn]


=== TEST 3: Parse URI fills in defaults correctly, using backwards compatible mode
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require("resty.http").new()

            local function test_uri(uri)
                local scheme, host, port, path, query = unpack(http:parse_uri(uri))
                ngx.say("scheme: ", scheme, ", host: ", host, ", port: ", port, ", path: ", path)
            end

            test_uri("http://example.com")
            test_uri("http://example.com/")
            test_uri("https://example.com/foo/bar")
            test_uri("https://example.com/foo/bar?a=1&b=2")
            test_uri("http://example.com?a=1&b=2")
            test_uri("//example.com")
            test_uri("//example.com?a=1&b=2")
            test_uri("//example.com/foo/bar?a=1&b=2")
        ';
    }
--- request
GET /a
--- response_body
scheme: http, host: example.com, port: 80, path: /
scheme: http, host: example.com, port: 80, path: /
scheme: https, host: example.com, port: 443, path: /foo/bar
scheme: https, host: example.com, port: 443, path: /foo/bar?a=1&b=2
scheme: http, host: example.com, port: 80, path: /?a=1&b=2
scheme: http, host: example.com, port: 80, path: /
scheme: http, host: example.com, port: 80, path: /?a=1&b=2
scheme: http, host: example.com, port: 80, path: /foo/bar?a=1&b=2
--- no_error_log
[error]
[warn]


=== TEST 4: IPv6 notation
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require("resty.http").new()

            local function test_uri(uri)
                local scheme, host, port, path, query = unpack(http:parse_uri(uri, false))
                ngx.say("scheme: ", scheme, ", host: ", host, ", port: ", port, ", path: ", path, ", query: ", query)
            end

            test_uri("http://[::1]")
            test_uri("http://[::1]/")
            test_uri("https://[::1]/foo/bar")
            test_uri("https://[::1]/foo/bar?a=1&b=2")
            test_uri("http://[::1]?a=1&b=2")
            test_uri("//[0:0:0:0:0:0:0:0]")
            test_uri("//[0:0:0:0:0:0:0:0]?a=1&b=2")
            test_uri("//[0:0:0:0:0:0:0:0]/foo/bar?a=1&b=2")
        ';
    }
--- request
GET /a
--- response_body
scheme: http, host: [::1], port: 80, path: /, query: 
scheme: http, host: [::1], port: 80, path: /, query: 
scheme: https, host: [::1], port: 443, path: /foo/bar, query: 
scheme: https, host: [::1], port: 443, path: /foo/bar, query: a=1&b=2
scheme: http, host: [::1], port: 80, path: /, query: a=1&b=2
scheme: http, host: [0:0:0:0:0:0:0:0], port: 80, path: /, query: 
scheme: http, host: [0:0:0:0:0:0:0:0], port: 80, path: /, query: a=1&b=2
scheme: http, host: [0:0:0:0:0:0:0:0], port: 80, path: /foo/bar, query: a=1&b=2
--- no_error_log
[error]
[warn]
