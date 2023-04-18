# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/t/openssl/x509/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
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
=== TEST 1: Creates stack properly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extensions = require("resty.openssl.x509.extensions")
            local c = myassert(extensions.new())

            ngx.say(#c)
        }
    }
--- request
    GET /t
--- response_body eval
"0
"
--- no_error_log
[error]

=== TEST 2: Adds elements to stack properly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension_lib = require("resty.openssl.x509.extension")
            local ext = extension_lib.new("extendedKeyUsage", "serverAuth,clientAuth")
            local extensions = require("resty.openssl.x509.extensions")
            local c = myassert(extensions.new())

            for i=0,2,1 do
                local ok = myassert(c:add(ext))
            end
            ngx.say(#c)
            ngx.say(#c:all())
        }
    }
--- request
    GET /t
--- response_body eval
"3
3
"
--- no_error_log
[error]

=== TEST 3: Element can be indexed properly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension_lib = require("resty.openssl.x509.extension")
            local ext = extension_lib.new("extendedKeyUsage", "serverAuth,clientAuth")
            local extensions = require("resty.openssl.x509.extensions")
            local c = myassert(extensions.new())

            for i=0,2,1 do
                local ok = myassert(c:add(ext))
            end

            collectgarbage()
            
            for _, cc in ipairs(c) do
                ngx.say(cc:text())
            end
        }
    }
--- request
    GET /t
--- response_body eval
"TLS Web Server Authentication, TLS Web Client Authentication
TLS Web Server Authentication, TLS Web Client Authentication
TLS Web Server Authentication, TLS Web Client Authentication
"
--- no_error_log
[error]

=== TEST 4: Element is duplicated when added to stack
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension_lib = require("resty.openssl.x509.extension")
            local ext = extension_lib.new("extendedKeyUsage", "serverAuth,clientAuth")
            local extensions = require("resty.openssl.x509.extensions")
            local c = myassert(extensions.new())

            local ok = myassert(c:add(ext))

            ext = nil
            collectgarbage("collect")
            ngx.say(c[1]:text())
        }
    }
--- request
    GET /t
--- response_body eval
"TLS Web Server Authentication, TLS Web Client Authentication
"
--- no_error_log
[error]

=== TEST 5: Element is duplicated when returned
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension_lib = require("resty.openssl.x509.extension")
            local ext = extension_lib.new("extendedKeyUsage", "serverAuth,clientAuth")
            local extensions = require("resty.openssl.x509.extensions")
            local c = myassert(extensions.new())

            local ok = myassert(c:add(ext))

            local cc = c[1]
            c = nil
            collectgarbage("collect") 
            ngx.say(cc:text())
        }
    }
--- request
    GET /t
--- response_body eval
"TLS Web Server Authentication, TLS Web Client Authentication
"
--- no_error_log
[error]

=== TEST 6: Element is not freed when stack is duplicated
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension_lib = require("resty.openssl.x509.extension")
            local ext = extension_lib.new("extendedKeyUsage", "serverAuth,clientAuth")
            local extensions = require("resty.openssl.x509.extensions")
            local c = myassert(extensions.new())

            local ok = myassert(c:add(ext))

            local c2 = myassert(extensions.dup(c.ctx))

            c = nil
            collectgarbage("collect") 
            ngx.say(c2:count())
            ngx.say(c2[1]:text())
        }
    }
--- request
    GET /t
--- response_body eval
"1
TLS Web Server Authentication, TLS Web Client Authentication
"
--- no_error_log
[error]
