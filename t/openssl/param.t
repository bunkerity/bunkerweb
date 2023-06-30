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
        _G.encode_sorted_json = require("helper").encode_sorted_json
    }
};

run_tests();

__DATA__
=== TEST 1: Construct
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            ngx.say("TODO")
        }
    }
--- request
    GET /t
--- response_body
TODO
--- no_error_log
[error]
