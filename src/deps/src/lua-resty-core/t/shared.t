# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * blocks() * 4;

our $HttpConfig = <<_EOC_;
    lua_shared_dict dogs 1m;
    $t::TestCore::HttpConfig
_EOC_

no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: shared.ttl errors on nil key
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ttl, err = ngx.shared.dogs:ttl()
            if not ttl then
                ngx.say("failed to get ttl: ", err)
            end
        }
    }
--- request
GET /t
--- response_body
failed to get ttl: nil key
--- no_error_log
[error]
[alert]



=== TEST 2: shared.ttl errors on empty key
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ttl, err = ngx.shared.dogs:ttl("")
            if not ttl then
                ngx.say("failed to get ttl: ", err)
            end
        }
    }
--- request
GET /t
--- response_body
failed to get ttl: empty key
--- no_error_log
[error]
[alert]



=== TEST 3: shared.ttl returns error on not found key
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.say("failed to get ttl: ", err)
            end
        }
    }
--- request
GET /t
--- response_body
failed to get ttl: not found
--- no_error_log
[error]
[alert]



=== TEST 4: shared.ttl returns key ttl for non-default (positive) ttl
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ok, err = ngx.shared.dogs:set("key", true, 0.2)

            local ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.log(ngx.ERR, "failed to get ttl: ", err)
            end

            ngx.say(ttl)

            ngx.say("sleep for 0.1s...")
            ngx.sleep(0.1)

            ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.log(ngx.ERR, "failed to get ttl: ", err)
            end

            ngx.say(ttl)
        }
    }
--- request
GET /t
--- response_body_like chomp
\A0.2
sleep for 0.1s...
0.\d*
\z
--- no_error_log
[error]
[alert]



=== TEST 5: shared.ttl returns key ttl for non-default (negative) ttl
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ok, err = ngx.shared.dogs:set("key", true, 0.1)

            local ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.log(ngx.ERR, "failed to get ttl: ", err)
            end

            ngx.say(ttl)

            ngx.say("sleep for 0.2s...")
            ngx.sleep(0.2)

            ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.log(ngx.ERR, "failed to get ttl: ", err)
            end

            ngx.say(ttl)
        }
    }
--- request
GET /t
--- response_body_like chomp
\A0.1
sleep for 0.2s...
-0.\d*
\z
--- no_error_log
[error]
[alert]



=== TEST 6: shared.ttl returns key ttl for default ttl (0)
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ok, err = ngx.shared.dogs:set("key", true)

            local ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.log(ngx.ERR, "failed to get ttl: ", err)
            end

            ngx.say(ttl)

            ngx.say("sleep for 0.1s...")
            ngx.sleep(0.11)

            ttl, err = ngx.shared.dogs:ttl("key")
            if not ttl then
                ngx.log(ngx.ERR, "failed to get ttl: ", err)
            end

            ngx.say(ttl)
        }
    }
--- request
GET /t
--- response_body
0
sleep for 0.1s...
0
--- no_error_log
[error]
[alert]



=== TEST 7: shared.ttl JIT compiles
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local ok, err = ngx.shared.dogs:set("key", true)

            for i = 1, 30 do
                local ttl, err = ngx.shared.dogs:ttl("key")
                if not ttl then
                    ngx.log(ngx.ERR, "failed to get ttl: ", err)
                end
            end
        }
    }
--- request
GET /t
--- response_body

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]



=== TEST 8: shared.expire errors on invalid exptime
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = pcall(dogs.expire, dogs)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- request
GET /t
--- response_body
bad "exptime" argument
--- no_error_log
[error]
[alert]



=== TEST 9: shared.expire returns error on nil key
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = dogs:expire(nil, 1)
            if not ok then
                ngx.say("failed to set ttl: ", err)
            end
        }
    }
--- request
GET /t
--- response_body
failed to set ttl: nil key
--- no_error_log
[error]
[alert]



=== TEST 10: shared.expire returns error on empty key
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = dogs:expire("", 1)
            if not ok then
                ngx.say("failed to set ttl: ", err)
            end
        }
    }
--- request
GET /t
--- response_body
failed to set ttl: empty key
--- no_error_log
[error]
[alert]



=== TEST 11: shared.expire returns error on not found key
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = dogs:expire("key", 1)
            if not ok then
                ngx.say("failed to set ttl: ", err)
            end
        }
    }
--- request
GET /t
--- response_body
failed to set ttl: not found
--- no_error_log
[error]
[alert]



=== TEST 12: shared.expire updates ttl of key with non-default ttl
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = dogs:set("key", true, 0.1)
            if not ok then
                ngx.log(ngx.ERR, "failed to set: ", err)
            end

            ok, err = dogs:expire("key", 0.3)
            if not ok then
                ngx.say("failed to set ttl: ", err)
            end

            ngx.sleep(0.2)

            local val, err = dogs:get("key")
            if err then
                ngx.log(ngx.ERR, "failed to get: ", err)
            end

            ngx.say("after 0.2s: ", val)

            ngx.sleep(0.2)

            val, err = dogs:get("key")
            if err then
                ngx.log(ngx.ERR, "failed to get: ", err)
            end

            ngx.say("after 0.4s: ", val)
        }
    }
--- request
GET /t
--- response_body
after 0.2s: true
after 0.4s: nil
--- no_error_log
[error]
[alert]



=== TEST 13: shared.expire updates ttl of key with default ttl (0)
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = dogs:set("key", true)
            if not ok then
                ngx.log(ngx.ERR, "failed to set: ", err)
            end

            local val, err = dogs:get("key")
            if err then
                ngx.log(ngx.ERR, "failed to get: ", err)
            end

            ngx.say("after set: ", val)

            ok, err = dogs:expire("key", 0.3)
            if not ok then
                ngx.say("failed to set ttl: ", err)
            end

            ngx.sleep(0.4)

            val, err = dogs:get("key")
            if err then
                ngx.log(ngx.ERR, "failed to get: ", err)
            end

            ngx.say("after 0.4s: ", val)
        }
    }
--- request
GET /t
--- response_body
after set: true
after 0.4s: nil
--- no_error_log
[error]
[alert]



=== TEST 14: shared.expire JIT compiles
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            local dogs = ngx.shared.dogs

            local ok, err = dogs:set("key", true, 0.1)
            if not ok then
                ngx.log(ngx.ERR, "failed to set: ", err)
            end

            for i = 1, 30 do
                local ok, err = dogs:expire("key", 0.3)
                if not ok then
                    ngx.say("failed to set ttl: ", err)
                end
            end
        }
    }
--- request
GET /t
--- response_body

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):9 loop\]/
--- no_error_log
[error]
