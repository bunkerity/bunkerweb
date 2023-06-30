# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end
    }
};

run_tests();

__DATA__
=== TEST 1: Prints version text properly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            ngx.say(version.version_text)
        }
    }
--- request
    GET /t
--- response_body_like
(OpenSSL \d.\d.\d.+|BoringSSL)
--- no_error_log
[error]

=== TEST 2: Prints version text using version()
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            ngx.say(version.version(version.VERSION))
            ngx.say(version.version(version.CFLAGS))
        }
    }
--- request
    GET /t
--- response_body_like
(OpenSSL \d.\d.\d.+|BoringSSL)
compiler:.+
--- no_error_log
[error]
