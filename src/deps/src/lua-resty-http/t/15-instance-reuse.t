use Test::Nginx::Socket 'no_plan';
use Cwd qw(cwd);

my $pwd = cwd();

$ENV{TEST_NGINX_RESOLVER} = '8.8.8.8';
$ENV{TEST_NGINX_PWD} ||= $pwd;
$ENV{TEST_COVERAGE} ||= 0;

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;;";

    init_by_lua_block {
        if $ENV{TEST_COVERAGE} == 1 then
            jit.off()
            require("luacov.runner").init()
        end
    }
};

no_long_string();
no_diff();

run_tests();


__DATA__
=== TEST 1: Reuse an instance connecting on different ports / paths
--- http_config eval: $::HttpConfig
--- config
location /a {
    content_by_lua_block {
        local httpc = require("resty.http").new()

        assert(httpc:connect("127.0.0.1", ngx.var.server_port),
            "connect should return positively")

        local res1 = httpc:request({ path = "/b" })
        ngx.print(res1:read_body())

        local res2 = httpc:request({ path = "/c" })
        ngx.print(res2:read_body())

        assert(res1 ~= res2, "responses should be unique tables")
        assert(res1.headers ~= res2.headers, "headers should be unique tables")

        assert(httpc:connect("127.0.0.1", 12345),
            "connect should return positively")

        local res3 = httpc:request({ path = "/b" })
        ngx.print(res3:read_body())

        assert(res3 ~= res2, "responses should be unique tables")
        assert(res3.headers ~= res2.headers, "headers should be unique tables")

        assert(httpc.keepalive == false, "keepalive flag should be false")

        assert(httpc:connect("127.0.0.1", ngx.var.server_port),
            "connect should return positively")

        assert(httpc.keepalive == true, "keepalive flag should be true")

    }
}
location /b {
    echo "b";
}
location /c {
    echo "c";
}
--- tcp_listen: 12345
--- tcp_reply
HTTP/1.0 200 OK
Date: Fri, 08 Aug 2016 08:12:31 GMT
Server: OpenResty

d
--- request
GET /a
--- response_body
b
c
d
--- no_error_log
[error]


=== TEST 2: Reuse input params table
--- http_config eval: $::HttpConfig
--- config
location /a {
    content_by_lua_block {
        local httpc = require("resty.http").new()

        assert(httpc:connect("127.0.0.1", ngx.var.server_port),
            "connect should return positively")

        local params = {
            path = "/b",
            method = "HEAD",
        }

        local res, err = httpc:request(params)
        assert(res, "request should return positvely")

        assert(not params.headers, "params table should not be modified")

        local res, err =
            httpc:request_uri("http://127.0.0.1:"..ngx.var.server_port, params)
        assert(res, "request_uri should return positvely")

        assert(not params.headers, "params table should not be modified")


        assert(httpc:connect("127.0.0.1", ngx.var.server_port),
            "connect should return positively")

        local pipeline_params = {
            { path = "/b", method = "POST" },
            { path = "/b", method = "HEAD" },
        }

        local res, err = httpc:request_pipeline(pipeline_params)
        assert(res, "request_pipeline should return positively")

        assert(not pipeline_params[1].headers and not pipeline_params[2].headers,
            "params tables should not be modified")

    }
}
location /b {
    echo "b";
}
--- request
GET /a
--- response_body
--- no_error_log
[error]
