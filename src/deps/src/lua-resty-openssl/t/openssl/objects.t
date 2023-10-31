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
=== TEST 1: Convert nid to table
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local o = require("resty.openssl.objects")
            ngx.print(encode_sorted_json(o.nid2table(87)))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":"2.5.29.19","ln":"X509v3 Basic Constraints","nid":87,"sn":"basicConstraints"}'
--- no_error_log
[error]


=== TEST 2: Convert txt to nid
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local o = require("resty.openssl.objects")
            local t = {
                ln = "X509v3 Basic Constraints",
                sn = "basicConstraints",
                id = "2.5.29.19"
            }
            local r = {}
            for k, v in pairs(t) do
                r[k] = o.txt2nid(v)
            end
            ngx.print(encode_sorted_json(r))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":87,"ln":87,"sn":87}'
--- no_error_log
[error]

=== TEST 3: Convert sigid to nid
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local o = require("resty.openssl.objects")
            ngx.print(o.find_sigid_algs(795)) -- ecdsa-with-SHA384
        }
    }
--- request
    GET /t
--- response_body eval
673
--- no_error_log
[error]