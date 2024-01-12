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
=== TEST 1: Old connect syntax still works
--- http_config eval: $::HttpConfig
--- config
    location /a {
        content_by_lua_block {
            local http = require "resty.http"
            local httpc = http.new()
            local ok, err = httpc:connect("127.0.0.1", ngx.var.server_port)
            assert(ok, err)

            local res, err = httpc:request{
                path = "/b"
            }

            ngx.status = res.status
            ngx.print(res:read_body())

            httpc:close()
        }
    }
    location = /b {
        echo "OK";
    }
--- request
GET /a
--- response_body
OK
--- no_error_log
[error]
[warn]
--- error_log
[debug]
