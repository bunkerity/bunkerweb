use Test::Nginx::Socket 'no_plan';
use Cwd qw(cwd);

my $pwd = cwd();

$ENV{TEST_COVERAGE} ||= 0;

our $HttpConfig = qq{
lua_package_path "$pwd/lib/?.lua;;";

init_by_lua_block {
    if $ENV{TEST_COVERAGE} == 1 then
        jit.off()
        require("luacov.runner").init()
    end
}

underscores_in_headers On;
};

no_long_string();
no_diff();

run_tests();

__DATA__
=== TEST 1: Unit test header normalisation
--- http_config eval: $::HttpConfig
--- config
location = /a {
    content_by_lua_block {
        local headers = require("resty.http_headers").new()

        headers["content-length"] = "a"
        headers["TRANSFER-ENCODING"] = "b"
        headers["SSL_CLIENT_CERTIFICATE"] = "foo"

        assert(headers["coNtENt-LENgth"] == headers["content-length"],
            "header values should match")

        assert(headers["transfer-encoding"] == headers["TRANSFER-ENCODING"],
            "header values should match")

        assert(headers["ssl_client_certificate"] == headers["SSL_CLIENT_CERTIFICATE"],
            "header values should match")

        assert(headers["SSL-CLIENT-CERTIFICATE"] ~= headers["SSL_CLIENT_CERTIFICATE"],
            "underscores are separate to hyphens")

    }
}
--- request
GET /a
--- response_body
--- no_error_log
[error]


=== TEST 2: Integration test headers normalisation
--- http_config eval: $::HttpConfig
--- config
location = /a {
    content_by_lua_block {
        local httpc = require("resty.http").new()
        assert(httpc:connect("127.0.0.1", ngx.var.server_port),
            "connect should return positively")

        local res, err = httpc:request{
            path = "/b"
        }

        ngx.status = res.status
        ngx.say(res.headers["X-Foo-Header"])
        ngx.say(res.headers["x-fOo-heaDeR"])

        httpc:close()
    }
}
location = /b {
    content_by_lua_block {
        ngx.header["X-Foo-Header"] = "bar"
        ngx.say("OK")
    }
}
--- request
GET /a
--- response_body
bar
bar
--- no_error_log
[error]


=== TEST 3: Integration test request headers normalisation
--- http_config eval: $::HttpConfig
--- config
location = /a {
    content_by_lua_block {
        local httpc = require("resty.http").new()
        assert(httpc:connect("127.0.0.1", ngx.var.server_port),
            "connect should return positively")

        local res, err = httpc:request{
            path = "/b",
            headers = {
                ["uSeR-AgENT"] = "test_user_agent",
                ["X_Foo"] = "bar",
            },
        }

        ngx.status = res.status
        ngx.print(res:read_body())

        httpc:close()
    }
}
location = /b {
    content_by_lua_block {
        ngx.say(ngx.req.get_headers()["User-Agent"])
        ngx.say(ngx.req.get_headers(nil, true)["X_Foo"])
    }
}
--- request
GET /a
--- response_body
test_user_agent
bar
--- no_error_log
[error]


=== TEST 4: Test that headers remain unique
--- http_config eval: $::HttpConfig
--- config
location = /a {
    content_by_lua_block {
        local headers = require("resty.http_headers").new()

        headers["x-a-header"] = "a"
        headers["X-A-HEAder"] = "b"

        for k,v in pairs(headers) do
            ngx.header[k] = v
        end
    }
}
--- request
GET /a
--- response_headers
x-a-header: b
--- no_error_log
[error]


=== TEST 5: Prove header tables are always unique
--- http_config eval: $::HttpConfig
--- config
location = /a {
    content_by_lua_block {
        local headers = require("resty.http_headers").new()

        headers["content-length"] = "a"
        headers["TRANSFER-ENCODING"] = "b"
        headers["SSL_CLIENT_CERTIFICATE"] = "foo"

        local headers2 = require("resty.http_headers").new()

        assert(headers2 ~= headers,
            "headers should be unique")

        assert(not next(headers2),
            "headers2 should be empty")

        assert(not next(getmetatable(headers2).normalised),
            "headers normalised data should be empty")
    }
}
--- request
GET /a
--- response_body
--- no_error_log
[error]
