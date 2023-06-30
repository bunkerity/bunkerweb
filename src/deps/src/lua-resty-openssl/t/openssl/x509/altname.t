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
=== TEST 1: Creates stack properly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())
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
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())

            for i=0,2,1 do
                local ok = myassert(c:add("DNS", string.format("%d.com", i)))
            end
            ngx.say(#c)
            ngx.say(c:count())
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
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())

            for i=0,2,1 do
                local ok = myassert(c:add("DNS", string.format("%d.com", i)))
            end
            for k, v in pairs(c) do
                ngx.say(k, " ", v)
            end
        }
    }
--- request
    GET /t
--- response_body eval
"DNS 0.com
DNS 1.com
DNS 2.com
"
--- no_error_log
[error]

=== TEST 4: Element is duplicated when added to stack
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())

            local ok = myassert(c:add("DNS", "example.com"))

            cert = nil
            collectgarbage("collect")
            local k, v = unpack(c[1])
            ngx.say(k, " ", v)
        }
    }
--- request
    GET /t
--- response_body eval
"DNS example.com
"
--- no_error_log
[error]

=== TEST 5: Element is duplicated when returned
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())

            local ok = myassert(c:add("DNS", "example.com"))

            local cc = c[1]
            c = nil
            collectgarbage("collect")
            if cc ~= nil then
                local k, v = unpack(cc)
                ngx.say(k, " ", v)
            else
                ngx.say("incorrectly GC'ed")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"DNS example.com
"
--- no_error_log
[error]

=== TEST 6: Element is not freed when stack is duplicated
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())

            local ok = myassert(c:add("DNS", "example.com"))

            local c2 = myassert(altname.dup(c.ctx))

            c = nil
            collectgarbage("collect")
            ngx.say(c2:count())
            local k, v = unpack(c2[1])
            ngx.say(k, " ", v)
        }
    }
--- request
    GET /t
--- response_body eval
"1
DNS example.com
"
--- no_error_log
[error]

=== TEST 7: Unsupported SANs are returned as "unsupported"
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local x509 = require("resty.openssl.x509")

            local extension = require "resty.openssl.x509.extension"

            local ext, err = myassert(extension.new("subjectAltName", "otherName:msUPN;UTF8:sb@sb.local,IP.1:255.255.255.255,IP.2:1111:1111:1111:1111:1111:1111:1111:1111,DNS:example.com,email:test@test.com,RID:1.2.3.4"))

            local c = x509.new()

            myassert(c:add_extension(ext))

            local alts = myassert(c:get_subject_alt_name())

            for k, v in pairs(alts) do
                ngx.say(k, ":", v)
            end
        }
    }
--- request
    GET /t
--- response_body
OtherName:OtherName:<unsupported>
IP:255.255.255.255
IP:1111:1111:1111:1111:1111:1111:1111:1111
DNS:example.com
email:test@test.com
RID:RID:<unsupported>
--- no_error_log
[error]

=== TEST 8: IP addresses are validated and parsed
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname")
            local c = myassert(altname.new())

            myassert(c:add("IP", "1.2.3.4"))
            myassert(c:add("IPAddress", "100.100.100.100"))
            myassert(c:add("IP", "255.255.255.255"))
            myassert(c:add("IP", "::1"))
            myassert(c:add("IP", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"))
            for _, v in ipairs({"1", ":::", "ffff:", "256.1.1.1"}) do
                local _, err = c:add("IP", v)
                if err == nil then
                    ngx.say("should error on " .. v)
                end
            end

            ngx.say(c:tostring())

        }
    }
--- request
    GET /t
--- response_body
IP=1.2.3.4/IP=100.100.100.100/IP=255.255.255.255/IP=::1/IP=ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff
--- no_error_log
[error]