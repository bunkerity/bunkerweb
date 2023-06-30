# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


repeat_each(2);

my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

add_block_preprocessor(sub {
    my ($block) = @_;

    my $name = $block->name;

    my $http_config = $block->http_config;

    if (defined $http_config ) {

        my $new_http_config = <<_EOC_;
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";

    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end
        _G.myassert = require("helper").myassert
        _G.encode_sorted_json = require("helper").encode_sorted_json
    }

    ssl_certificate $pwd/t/fixtures/test.crt;
    ssl_certificate_key $pwd/t/fixtures/test.key;

    lua_ssl_trusted_certificate $pwd/t/fixtures/test.crt;

$http_config

_EOC_

        $block->set_value("http_config", $new_http_config);
    }

});


our $ClientContentBy = qq{

};

no_long_string();

env_to_nginx("CI_SKIP_NGINX_C");

run_tests();

__DATA__
=== TEST 1: SSL (server) get peer certificate
--- http_config
    server {
        listen unix:/tmp/nginx-sctx1.sock ssl;
        server_name   test.com;

        ssl_certificate_by_lua_block {
            local ssl_ctx = require "resty.openssl.ssl_ctx"
            local sc = assert(ssl_ctx.from_request())
            assert(sc:set_alpns({"h4"}))
        }
    }
--- config
    location /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local opts = {
                merge_stderr = true,
                buffer_size = 256000,
            }
            local proc = ngx_pipe.spawn({'bash', '-c', "echo q | openssl s_client -unix /tmp/nginx-sctx1.sock -alpn h4 && sleep 0.1"}, opts)
            local data, err, partial = proc:stdout_read_all()
            if ngx.re.match(data, "ALPN protocol: h4") then
                ngx.say("ok")
            else
                ngx.say(data)
            end
        }
    }
--- request
    GET /t
--- response_body
ok

--- no_error_log
[error]
[emerg]

