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
=== TEST 1: parse_uri returns port 443 for https URIs
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local parsed = httpc:parse_uri("https://www.google.com/foobar")
            ngx.say(parsed[3])
        ';
    }
--- request
GET /a
--- response_body
443
--- no_error_log
[error]
[warn]


=== TEST 2: parse_uri returns port 80 for http URIs
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            local parsed = httpc:parse_uri("http://www.google.com/foobar")
            ngx.say(parsed[3])
        ';
    }
--- request
GET /a
--- response_body
80
--- no_error_log
[error]
[warn]
