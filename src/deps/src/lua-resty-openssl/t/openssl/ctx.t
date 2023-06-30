# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end
        _G.myassert = require("helper").myassert
    }
};

run_tests();

__DATA__
=== TEST 1: Can create a ctx in ngx.ctx
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.exit(0)
            end
            local ctx = require("resty.openssl.ctx")
            myassert(ctx.new(true))
        }
    }
--- request
    GET /t
--- no_error_log
[error]


=== TEST 2: Can create a ctx in global namespace
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.exit(0)
            end
            local ctx = require("resty.openssl.ctx")
            myassert(ctx.new())
        }
    }
--- request
    GET /t
--- no_error_log
[error]


=== TEST 3: Can free ctx in ngx.ctx
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.exit(0)
            end
            local ctx = require("resty.openssl.ctx")
            myassert(ctx.new(true))
            myassert(ctx.free(true))
        }
    }
--- request
    GET /t
--- no_error_log
[error]


=== TEST 4: Can free ctx in global namespace
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.exit(0)
            end
            local ctx = require("resty.openssl.ctx")
            myassert(ctx.new())
            myassert(ctx.free())
        }
    }
--- request
    GET /t
--- no_error_log
[error]
