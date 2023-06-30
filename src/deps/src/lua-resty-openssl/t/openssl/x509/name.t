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
=== TEST 1: Duplicate the ctx
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            require('ffi').cdef('typedef struct X509_name_st X509_NAME; void X509_NAME_free(X509_NAME *name);')
            local name = myassert(require("resty.openssl.x509.name").new())

            local name2 = myassert(require("resty.openssl.x509.name").dup(name.ctx))

            name = nil
            collectgarbage("collect")
            -- if name2.ctx is also freed this following will segfault
            local _ = myassert(name2:add("CN", "example.com"))

        }
    }
--- request
    GET /t
--- response_body eval
""
--- no_error_log
[error]

=== TEST 2: Rejects invalid NID
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local name = myassert(require("resty.openssl.x509.name").new())

            name, err = name:add("whatever", "value")
            ngx.say(name == nil)
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body eval
"true
x509.name:add: invalid NID text whatever
"
--- no_error_log
[error]

=== TEST 3: Finds by text
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local name = myassert(require("resty.openssl.x509.name").new())

            name = myassert(name:add("CN", "example.com"))
 
            name = myassert(name:add("CN", "anotherdomain.com"))

            local a, b, c = name:find("CN")
            if a then
                ngx.say("found ", b, " ", a.blob)
            end
            local a, b, c = name:find("2.5.4.3")
            if a then
                ngx.say("found ", b, " ", a.blob)
            end
            local a, b, c = name:find("CM")
            if not a then
                ngx.say("not found")
            end
            local a, b, c = name:find("CN", 1)
            if a then
                ngx.say("found ", b, " ", a.blob)
            end
        }
    }
--- request
    GET /t
--- response_body_like eval
"found 1 example.com
found 1 example.com
not found
found 2 anotherdomain.com
"
--- no_error_log
[error]


=== TEST 4: Pairs
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local name = myassert(require("resty.openssl.x509.name").new())

            local CNs = 3
            for i=1,CNs,1 do
                name = myassert(name:add("CN", string.format("%d.example.com", i)))
            end
            local others = { "L", "ST", "O" }
            for _, k in ipairs(others) do
                name = myassert(name:add(k, "Mars"))
            end
            ngx.say(#name)
            for k, v in pairs(name) do
                ngx.print(v.nid .. ",")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"6
13,13,13,15,16,17,"
--- no_error_log
[error]