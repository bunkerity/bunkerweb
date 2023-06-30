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
=== TEST 1: Calculate digest correctly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local digest = myassert(require("resty.openssl.digest").new("sha256"))

            myassert(digest:update("🦢🦢🦢🦢🦢🦢"))
            ngx.print(ngx.encode_base64(myassert(digest:final())))
        }
    }
--- request
    GET /t
--- response_body eval
"2iuYqSWdAyVAtQxL/p+AOl2kqp83fN4k+da6ngAt8+s="
--- no_error_log
[error]

=== TEST 2: Update accepts vardiac args
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local digest = myassert(require("resty.openssl.digest").new("sha256"))

            myassert(digest:update("🦢", "🦢🦢", "🦢🦢", "🦢"))
            ngx.print(ngx.encode_base64(myassert(digest:final())))
        }
    }
--- request
    GET /t
--- response_body eval
"2iuYqSWdAyVAtQxL/p+AOl2kqp83fN4k+da6ngAt8+s="
--- no_error_log
[error]

=== TEST 3: Final accepts optional arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local digest = myassert(require("resty.openssl.digest").new("sha256"))

            myassert(digest:update("🦢", "🦢🦢", "🦢🦢"))
            ngx.print(ngx.encode_base64(myassert(digest:final("🦢"))))
        }
    }
--- request
    GET /t
--- response_body eval
"2iuYqSWdAyVAtQxL/p+AOl2kqp83fN4k+da6ngAt8+s="
--- no_error_log
[error]

=== TEST 4: Rejects unknown hash
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local digest, err = require("resty.openssl.digest").new("sha257")
            ngx.print(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"digest.new: invalid digest type \"sha257\".*"
--- no_error_log
[error]

=== TEST 5: Can be reused
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local digest = myassert(require("resty.openssl.digest").new("sha256"))

            myassert(digest:update("🦢🦢🦢🦢🦢🦢"))
            ngx.say(ngx.encode_base64(myassert(digest:final())))

            myassert(digest:reset())
            myassert(digest:update("🦢🦢🦢🦢🦢🦢"))
            ngx.say(ngx.encode_base64(myassert(digest:final())))
        }
    }
--- request
    GET /t
--- response_body eval
"2iuYqSWdAyVAtQxL/p+AOl2kqp83fN4k+da6ngAt8+s=
2iuYqSWdAyVAtQxL/p+AOl2kqp83fN4k+da6ngAt8+s=
"
--- no_error_log
[error]

=== TEST 6: Returns provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("default")
                ngx.exit(0)
            end

            local digest = require("resty.openssl.digest")
            local d = myassert(digest.new("sha256"))
            ngx.say(myassert(d:get_provider_name()))
        }
    }
--- request
    GET /t
--- response_body
default
--- no_error_log
[error]

=== TEST 7: Returns gettable, settable params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("{}\n-ssl3-ms-")
                ngx.exit(0)
            end

            local digest = require("resty.openssl.digest")
            local d = myassert(digest.new("md5-sha1"))
            ngx.say(require("cjson").encode(myassert(d:gettable_params())))
            ngx.say(require("cjson").encode(myassert(d:settable_params())))
        }
    }
--- request
    GET /t
--- response_body_like
{}
.+ssl3-ms.+
--- no_error_log
[error]

=== TEST 8: Get params, set params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            -- no good example to test
            ngx.say("skipped")
        }
    }
--- request
    GET /t
--- response_body eval
"skipped
"
--- no_error_log
[error]