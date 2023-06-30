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
=== TEST 1: New BIGNUM instance correctly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn, err = require("resty.openssl.bn").new()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn:to_binary()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(ngx.encode_base64(b))
        }
    }
--- request
    GET /t
--- response_body eval
""
--- error_log
bn:to_binary failed

=== TEST 2: New BIGNUM instance from number
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn, err = require("resty.openssl.bn").new(0x5b25)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn:to_binary()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(ngx.encode_base64(b))
        }
    }
--- request
    GET /t
--- response_body eval
"WyU="
--- no_error_log
[error]

=== TEST 3: Duplicate the ctx
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            require('ffi').cdef('typedef struct bignum_st BIGNUM; void BN_free(BIGNUM *a);')
            local bn, err = require("resty.openssl.bn").new(0x5b25)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local bn2, err = require("resty.openssl.bn").dup(bn.ctx)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            bn = nil
            collectgarbage("collect")
            local b, err = bn2:to_binary()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(ngx.encode_base64(b))
        }
    }
--- request
    GET /t
--- response_body eval
"WyU="
--- no_error_log
[error]

=== TEST 4: from_binary, to_binary
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local d = ngx.decode_base64('WyU=')
            local bn, err = require("resty.openssl.bn").from_binary(d)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn:to_binary()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(ngx.encode_base64(b))

            if not require("resty.openssl.version").OPENSSL_11_OR_LATER then
                ngx.print("AAAAAAAAAABbJQ=="); ngx.exit(0)
            end

            local b, err = bn:to_binary(10)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(ngx.encode_base64(b))
        }
    }
--- request
    GET /t
--- response_body eval
"WyU=AAAAAAAAAABbJQ=="
--- no_error_log
[error]

=== TEST 5: from_hex, to_hex
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn, err = require("resty.openssl.bn").from_hex("5B25")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn:to_hex()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(b)
        }
    }
--- request
    GET /t
--- response_body_like eval
"5[Bb]25"
--- no_error_log
[error]

=== TEST 6: from_dec, to_dec
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn, err = require("resty.openssl.bn").from_dec("23333")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn:to_dec()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.print(b)
        }
    }
--- request
    GET /t
--- response_body eval
"23333"
--- no_error_log
[error]

=== TEST 7: to_number
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local b, err = bn.new(23333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local n, err = b:to_number()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(n),type(n))

            b, err = bn.from_dec('184467440737095516161844674407370955161618446744073709551616')
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local n, err = b:to_number()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(n),type(n))

        }
    }
--- request
    GET /t
--- response_body eval
"23333number
1.844674407371e+19number
"
--- no_error_log
[error]

=== TEST 8: unary minus
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn, err = require("resty.openssl.bn").new(23333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = (-bn):to_dec()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(b)
            local b, err = (-(-bn)):to_dec()
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(b)
        }
    }
--- request
    GET /t
--- response_body eval
"-23333
23333
"
--- no_error_log
[error]

=== TEST 9: metamethods checks arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local a, err = require("resty.openssl.bn").new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = require("resty.openssl.bn").new(2478652)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local pok, perr = pcall(function() return a + "233" end)
            ngx.say(perr)
            local pok, perr = pcall(function() return "233" - a end)
            ngx.say(perr)
        }
    }
--- request
    GET /t
--- response_body_like eval
".+cannot add a string to bignum
.+cannot substract a string to bignum
"
--- no_error_log
[error]

=== TEST 10: add, sub, mul, div mod
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn.new(2478652)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(a+b))
            ngx.say(tostring(a-b))
            ngx.say(tostring(a*b))
            ngx.say(tostring(a/b))
            ngx.say(tostring(a%b))
            ngx.say(tostring(a*2478652))
            ngx.say(tostring(23578164761333*b))
            ngx.say(tostring(bn.mul(23578164761333, b)))
            ngx.say(tostring(a:mul(b)))
            ngx.say(tostring(23578164761333*2478652))
        }
    }
--- request
    GET /t
--- response_body eval
"23578167239985
23578162282681
58442065242007563116
9512495
4593
58442065242007563116
58442065242007563116
58442065242007563116
58442065242007563116
5.8442065242008e\+19
"
--- no_error_log
[error]

=== TEST 11: sqr, exp
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn.new(97)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(a:sqr()))
            ngx.say(tostring(a:exp(2)))
            ngx.say(tostring(a:pow(2)))
            ngx.say(tostring(b:exp(b)))
            ngx.say(tostring(bn.sqr(a)))
            ngx.say(tostring(bn.sqr(23578164761333)))
            ngx.say(tostring(bn.exp(a, 2)))
            ngx.say(tostring(bn.exp(23578164761333, 2)))
        }
    }
--- request
    GET /t
--- response_body eval
"555929853512565244851936889
555929853512565244851936889
555929853512565244851936889
5210245939718361468048211048414496022534389576033913164940029913016568215580398296261072019231723279851007241838011659882766685337218633992220688288491655299087016195985205218347711578485744737
555929853512565244851936889
555929853512565244851936889
555929853512565244851936889
555929853512565244851936889
"
--- no_error_log
[error]

=== TEST 12: gcd
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn.new(97)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(a:gcd(b)))
            ngx.say(tostring(bn.gcd(a, b)))
            ngx.say(tostring(bn.gcd(a, 97)))
            ngx.say(tostring(bn.gcd(23578164761333, b)))
        }
    }
--- request
    GET /t
--- response_body eval
"1
1
1
1
"
--- no_error_log
[error]

=== TEST 13: lshift, rshift
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(a:lshift(2)))
            ngx.say(tostring(a:rshift(2)))
        }
    }
--- request
    GET /t
--- response_body eval
"94312659045332
5894541190333
"
--- no_error_log
[error]

=== TEST 14: comparasion
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn.new(97)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(a == b))
            ngx.say(tostring(a ~= b))
            ngx.say(tostring(a >= b))
            ngx.say(tostring(a > b))
            ngx.say(tostring(a < b))
            ngx.say(tostring(a <= b))
            ngx.say("")
            ngx.say(tostring(a == a))
            ngx.say(tostring(a ~= a))
            ngx.say(tostring(a >= a))
            ngx.say(tostring(a > a))
            ngx.say(tostring(a < a))
            ngx.say(tostring(a <= a))
        }
    }
--- request
    GET /t
--- response_body eval
"false
true
true
true
false
false

true
false
true
false
false
true
"
--- no_error_log
[error]

=== TEST 15: is_one, is_zero, is_odd, is_word
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            ngx.say(tostring(bn.new(0):is_zero()))
            ngx.say(tostring(bn.new(1):is_zero()))
            ngx.say(tostring(bn.new(0):is_one()))
            ngx.say(tostring(bn.new(1):is_one()))
            ngx.say(tostring(bn.new(0):is_odd()))
            ngx.say(tostring(bn.new(1):is_odd()))
            ngx.say(tostring(bn.new(0):is_word(0)))
            ngx.say(tostring(bn.new(1):is_word(0)))
        }
    }
--- request
    GET /t
--- response_body eval
"true
false
false
true
false
true
true
false
"
--- no_error_log
[error]

=== TEST 16: is_prime
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            ngx.say(tostring(bn.new(2):is_prime()))
            ngx.say(tostring(bn.new(15):is_prime()))
            ngx.say(tostring(bn
            .from_hex('00d3277434ff7e3d410b3453a5cddc13e834fbdc19f38c580bc05b68dfa179afa4b6e6d34fe2bde9d90390046a86306bd022d4ed8187ccaa21808e189e7b803fd918b7782078f3be6bc8683d71d7d46cb134bc2a74dbe410d2bb068e45af95deef546f6970b83f9386e504b6fbefee6ae804fbf544e6b7cf82aacfff9472c6af07')
            :is_prime()))
        }
    }
--- request
    GET /t
--- response_body eval
"true
false
true
"
--- no_error_log
[error]

=== TEST 17: mod_add, mod_sub, mod_mul, mul_exp, mul_sqr mod
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.new(23578164761333)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local b, err = bn.new(2478652)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local m, err = bn.new(65537)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(a:mod_add(b, m)))
            ngx.say(tostring(a:mod_sub(b, m)))
            ngx.say(tostring(a:mod_mul(b, m)))
            ngx.say(tostring(a:mod_exp(b, m)))
            ngx.say(tostring(a:mod_sqr(b, m)))
            ngx.say(tostring(a:mod_exp(b, 65537)))
            ngx.say(tostring(bn.mod_exp(a, 2478652, m)))
        }
    }
--- request
    GET /t
--- response_body eval
"49755
7726
27398
28353
1266433
28353
28353
"
--- no_error_log
[error]

=== TEST 18: generate_prime
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local bn = require("resty.openssl.bn")
            local a, err = bn.generate_prime(10, false)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            if not a:is_prime() then
                ngx.log(ngx.ERR, "not prime")
                return
            end
            local a, err = bn.generate_prime(10, true)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            if not a:is_prime() then
                ngx.log(ngx.ERR, "not prime")
                return
            end
            ngx.say("ok")
        }
    }
--- request
    GET /t
--- response_body eval
"ok
"
--- no_error_log
[error]