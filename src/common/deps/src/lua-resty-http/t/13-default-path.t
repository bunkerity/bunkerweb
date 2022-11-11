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
=== TEST 1: request_uri (check the default path)
--- http_config eval: $::HttpConfig
--- config
    location /lua {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()

            local res, err = httpc:request_uri("http://127.0.0.1:"..ngx.var.server_port)

            if res and 200 == res.status then
                ngx.say("OK")
            else
                ngx.say("FAIL")
            end
        ';
    }

    location =/ {
        content_by_lua '
            ngx.print("OK")
        ';
    }
--- request
GET /lua
--- response_body
OK
--- no_error_log
[error]
