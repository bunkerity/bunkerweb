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
=== TEST 1: Geneartes random bytes
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local rand = require("resty.openssl.rand")
            local b, err = rand.bytes(233)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(#b)
            local b2, err = rand.bytes(233)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(#b2)
            ngx.say(b == b2)
        }
    }
--- request
    GET /t
--- response_body eval
"233
233
false
"
--- no_error_log
[error]


=== TEST 2: Rejects invalid arguments
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local rand = require("resty.openssl.rand")
            local b, err = rand.bytes()
            ngx.say(err)
            local b, err = rand.bytes(true)
            ngx.say(err)
            local b, err = rand.bytes({})
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body eval
"rand.bytes: expect a number at #1
rand.bytes: expect a number at #1
rand.bytes: expect a number at #1
"
--- no_error_log
[error]


