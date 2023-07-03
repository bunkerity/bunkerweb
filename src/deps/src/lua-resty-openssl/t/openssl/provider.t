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
        _G.encode_sorted_json = require("helper").encode_sorted_json
    }
};

run_tests();

__DATA__
=== TEST 1: Loads default and legacy provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("true\nnil\ntrue\nfalse\nnil\ntrue")
                ngx.exit(0)
            end

            local pro = require "resty.openssl.provider"
            for _, n in ipairs({"default", "legacy"}) do
                local avail, err = pro.is_available(n)
                ngx.say(avail)
                local p, err = pro.load(n)
                ngx.say(err)
                -- after load it's available
                local avail, err = pro.is_available(n)
                ngx.say(avail)

                myassert(p:unload())
            end
        }
    }
--- request
    GET /t
--- response_body
true
nil
true
false
nil
true
--- no_error_log
[error]

=== TEST 2: Self test default and legacy provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("nil\ntrue\nnil\ntrue")
                ngx.exit(0)
            end

            local pro = require "resty.openssl.provider"
            for _, n in ipairs({"default", "legacy"}) do
                local p, err = pro.load(n)
                ngx.say(err)
                -- after load it's available
                local ok, err = p:self_test(n)
                ngx.say(ok)

                myassert(p:unload())
            end
        }
    }
--- request
    GET /t
--- response_body
nil
true
nil
true
--- no_error_log
[error]

=== TEST 3: Set default search path
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("true\ncommon libcrypto routines::init fail")
                ngx.exit(0)
            end

            local pro = require "resty.openssl.provider"
            pro.set_default_search_path("/tmp")
            local ok, err = pro.load("legacy")
            ngx.say(ok == nil)
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like
true
.+(?:init fail|common libcrypto routines::reason\(524325\))
--- no_error_log
[error]

=== TEST 4: Get parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say('{"buildinfo":"3.0.0-alpha7","name":"OpenSSL Default Provider","status":1,"version":"3.0.0"}')
                ngx.exit(0)
            end

            local pro = require "resty.openssl.provider"
            local p = myassert(pro.load("default"))
            local a = assert(p:get_params("name", "version", "buildinfo", "status"))
            ngx.say(encode_sorted_json(a))
        }
    }
--- request
    GET /t
--- response_body_like
{"buildinfo":"3.+","name":"OpenSSL Default Provider","status":1,"version":"3.+"}
--- no_error_log
[error]

