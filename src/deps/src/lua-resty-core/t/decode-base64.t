# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5 - 2);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: string
--- config
    location = /base64 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.decode_base64("aGVsbG8=")
            end
            ngx.say(s)
        }
    }
--- request
GET /base64
--- response_body
hello
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 2: set base64 (nil)
--- config
    location = /base64 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.decode_base64("")
            end
            ngx.say(s)
        }
    }
--- request
GET /base64
--- response_body eval: "\n"
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 3: set base64 (number)
--- config
    location = /base64 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.decode_base64("My4xNA==")
            end
            ngx.say(s)
        }
    }
--- request
GET /base64
--- response_body
3.14
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 4: set base64 (boolean)
--- config
    location = /base64 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.decode_base64("dHJ1ZQ==")
            end
            ngx.say(s)
        }
    }
--- request
GET /base64
--- response_body
true
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 5: string (buf size just smaller than 4096)
--- config
    location = /base64 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.decode_base64(string.rep("a", 5460))
            end
            if not s then
                ngx.say("bad base64 string")
            else
                ngx.say(string.len(s))
            end
        }
    }
--- request
GET /base64
--- response_body
4095
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 6: string (buf size just a bit bigger than 4096)
--- config
    location = /base64 {
        content_by_lua_block {
            local s
            for i = 1, 100 do
                s = ngx.decode_base64(string.rep("a", 5462))
            end
            if not s then
                ngx.say("bad base64 string")
            else
                ngx.say(string.len(s))
            end
        }
    }
--- request
GET /base64
--- response_body
4096
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
 -- NYI:



=== TEST 7: decode_base64url
--- config
    location = /t {
        content_by_lua_block {
            local enc = require("ngx.base64")

            local function to_hex(str)
                return (str:gsub('.', function(c)
                    return string.format('%02x', string.byte(c))
                end))
            end

            -- RFC 4648 test vectors
            ngx.say("decode_base64url(\"\") = \"", enc.decode_base64url(""), "\"")
            ngx.say("decode_base64url(\"Zg\") = \"", enc.decode_base64url("Zg"), "\"")
            ngx.say("decode_base64url(\"Zm8\") = \"", enc.decode_base64url("Zm8"), "\"")
            ngx.say("decode_base64url(\"Zm9v\") = \"", enc.decode_base64url("Zm9v"), "\"")
            ngx.say("decode_base64url(\"Zm9vYg\") = \"", enc.decode_base64url("Zm9vYg"), "\"")
            ngx.say("decode_base64url(\"Zm9vYmE\") = \"", enc.decode_base64url("Zm9vYmE"), "\"")
            ngx.say("decode_base64url(\"Zm9vYmFy\") = \"", enc.decode_base64url("Zm9vYmFy"), "\"")
            ngx.say("decode_base64url(\"_w\") = \"\\x", to_hex(enc.decode_base64url("_w")), "\"")

            ngx.say("decode_base64url(\"YQBi\") = \"\\x", to_hex(enc.decode_base64url("YQBi")), "\"")
        }
    }
--- request
GET /t
--- response_body
decode_base64url("") = ""
decode_base64url("Zg") = "f"
decode_base64url("Zm8") = "fo"
decode_base64url("Zm9v") = "foo"
decode_base64url("Zm9vYg") = "foob"
decode_base64url("Zm9vYmE") = "fooba"
decode_base64url("Zm9vYmFy") = "foobar"
decode_base64url("_w") = "\xff"
decode_base64url("YQBi") = "\x610062"
--- no_error_log
[error]
[crit]



=== TEST 8: decode_base64url with invalid input
--- config
    location = /t {
        content_by_lua_block {
            local enc = require("ngx.base64")

            local res, err = enc.decode_base64url("     ")

            ngx.say("decode_base64url returned: ", res, ", ", err)
        }
    }
--- request
GET /t
--- response_body
decode_base64url returned: nil, invalid input
--- no_error_log
[error]
 -- NYI:
