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
=== TEST 1: Issue a notice (but do not error) if trying to read the request body in a subrequest
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        echo_location /b;
    }
    location = /b {
        content_by_lua '
            local http = require "resty.http"
            local httpc = http.new()
            httpc:connect({
                scheme = "http",
                host = "127.0.0.1",
                port = ngx.var.server_port,
            })

            local res, err = httpc:request{
                path = "/c",
                headers = {
                    ["Content-Type"] = "application/x-www-form-urlencoded",
                }
            }
            if not res then
                ngx.say(err)
            end
            ngx.print(res:read_body())
            httpc:close()
        ';
    }
    location /c {
        echo "OK";
    }
--- request
GET /a
--- response_body
OK
--- no_error_log
[error]
[warn]


=== TEST 2: Read request body
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua_block {
            local httpc = require("resty.http").new()

            local reader, err = assert(httpc:get_client_body_reader())

            repeat
                local buffer, err = reader()
                if err then
                    ngx.log(ngx.ERR, err)
                end

                if buffer then
                    ngx.print(buffer)
                end
            until not buffer
        }
    }
--- request
POST /a
foobar
--- response_body: foobar
--- no_error_log
[error]
[warn]


=== TEST 2: Read chunked request body, errors as not yet supported
--- http_config eval: $::HttpConfig
--- config
    location = /a {
        content_by_lua_block {
            local httpc = require("resty.http").new()
            local _, err = httpc:get_client_body_reader()
            ngx.log(ngx.ERR, err)
        }
    }
--- more_headers
Transfer-Encoding: chunked
--- request eval
"POST /a
3\r
foo\r
3\r
bar\r
0\r
\r
"
--- error_log
chunked request bodies not supported yet
--- no_error_log
[warn]
