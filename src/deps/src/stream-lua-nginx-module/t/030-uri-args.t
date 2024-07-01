# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

no_root_location();

#no_shuffle();
#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: ngx.encode_args (sanity)
--- stream_server_config
    content_by_lua_block {
        local t = {a = "bar", b = "foo"}
        ngx.say(ngx.encode_args(t))
    }
--- stream_response eval
qr/a=bar&b=foo|b=foo&a=bar/
--- no_error_log
[error]



=== TEST 2: ngx.encode_args (empty table)
--- stream_server_config
    content_by_lua_block {
        local t = {a = nil}
        ngx.say("args:" .. ngx.encode_args(t))
    }
--- stream_response
args:
--- no_error_log
[error]



=== TEST 3: ngx.encode_args (value is table)
--- stream_server_config
    content_by_lua_block {
        local t = {a = {9, 2}, b = 3}
        ngx.say("args:" .. ngx.encode_args(t))
    }
--- stream_response_like
(?x) ^args:
    (?= .*? \b a=9 \b )  # 3 chars
    (?= .*? \b a=2 \b )  # 3 chars
    (?= .*? \b b=3 \b )  # 3 chars
    (?= (?: [^&]+ & ){2} [^&]+ $ )  # requires exactly 2 &'s
    (?= .{11} $ )  # requires for total 11 chars (exactly) in the string
--- no_error_log
[error]



=== TEST 4: ngx.encode_args (boolean values)
--- stream_server_config
    content_by_lua_block {
        local t = {a = true, foo = 3}
        ngx.say("args: " .. ngx.encode_args(t))
    }
--- stream_response_like
^args: (?:a&foo=3|foo=3&a)$
--- no_error_log
[error]



=== TEST 5: ngx.encode_args (boolean values, false)
--- stream_server_config
    content_by_lua_block {
        local t = {a = false, foo = 3}
        ngx.say("args: " .. ngx.encode_args(t))
    }
--- stream_response
args: foo=3
--- no_error_log
[error]



=== TEST 6: boolean values in ngx.encode_args
--- stream_server_config
    content_by_lua_block {
        local t = {bar = {32, true}, foo = 3}
        ngx.say(ngx.encode_args(t))
    }
--- stream_response_like
(?x) ^
    (?= .*? \b bar=32 \b )     # 6 chars
    (?= .*? \b bar (?!=) \b )  # 3 chars
    (?= .*? \b foo=3 \b )      # 5 chars
    (?= (?: [^&]+ & ){2} [^&]+ $ )  # requires exactly 2 &'s
    (?= .{16} $ )  # requires for total 16 chars (exactly) in the string
--- no_error_log
[error]



=== TEST 7: ngx.encode_args (bad user data value)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local t = {bar = ngx.shared.dogs, foo = 3}
        rc, err = pcall(ngx.encode_args, t)
        ngx.say("rc: ", rc, ", err: ", err)
    }
--- stream_response
rc: false, err: attempt to use userdata as query arg value
--- no_error_log
[error]



=== TEST 8: ngx.encode_args (empty table)
--- stream_server_config
    content_by_lua_block {
        local t = {}
        ngx.say("args: ", ngx.encode_args(t))
    }
--- stream_response
args: 
--- no_error_log
[error]



=== TEST 9: ngx.encode_args (bad arg)
--- stream_server_config
    content_by_lua_block {
        local rc, err = pcall(ngx.encode_args, true)
        ngx.say("rc: ", rc, ", err: ", err)
    }
--- stream_response
rc: false, err: bad argument #1 to '?' (table expected, got boolean)
--- no_error_log
[error]



=== TEST 10: ngx.decode_args (sanity)
--- stream_server_config
    content_by_lua_block {
        local args = "a=bar&b=foo"
        args = ngx.decode_args(args)
        ngx.say("a = ", args.a)
        ngx.say("b = ", args.b)
    }
--- stream_response
a = bar
b = foo
--- no_error_log
[error]



=== TEST 11: ngx.decode_args (multi-value)
--- stream_server_config
    content_by_lua_block {
        local args = "a=bar&b=foo&a=baz"
        args = ngx.decode_args(args)
        ngx.say("a = ", table.concat(args.a, ", "))
        ngx.say("b = ", args.b)
    }
--- stream_response
a = bar, baz
b = foo
--- no_error_log
[error]



=== TEST 12: ngx.decode_args (empty string)
--- stream_server_config
    content_by_lua_block {
        local args = ""
        args = ngx.decode_args(args)
        ngx.say("n = ", #args)
    }
--- stream_response
n = 0
--- no_error_log
[error]



=== TEST 13: ngx.decode_args (boolean args)
--- stream_server_config
    content_by_lua_block {
        local args = "a&b"
        args = ngx.decode_args(args)
        ngx.say("a = ", args.a)
        ngx.say("b = ", args.b)
    }
--- stream_response
a = true
b = true
--- no_error_log
[error]



=== TEST 14: ngx.decode_args (empty value args)
--- stream_server_config
    content_by_lua_block {
        local args = "a=&b="
        args = ngx.decode_args(args)
        ngx.say("a = ", args.a)
        ngx.say("b = ", args.b)
    }
--- stream_response
a = 
b = 
--- no_error_log
[error]



=== TEST 15: ngx.decode_args (max_args = 1)
--- stream_server_config
    content_by_lua_block {
        local args = "a=bar&b=foo"
        args = ngx.decode_args(args, 1)
        ngx.say("a = ", args.a)
        ngx.say("b = ", args.b)
    }
--- stream_response
a = bar
b = nil
--- no_error_log
[error]



=== TEST 16: ngx.decode_args (max_args = -1)
--- stream_server_config
    content_by_lua_block {
        local args = "a=bar&b=foo"
        args = ngx.decode_args(args, -1)
        ngx.say("a = ", args.a)
        ngx.say("b = ", args.b)
    }
--- stream_response
a = bar
b = foo
--- no_error_log
[error]



=== TEST 17: ngx.decode_args should not modify lua strings in place
--- stream_server_config
    content_by_lua_block {
        local s = "f+f=bar&B=foo"
        args = ngx.decode_args(s)
        local arr = {}
        for k, v in pairs(args) do
            table.insert(arr, k)
        end
        table.sort(arr)
        for i, k in ipairs(arr) do
            ngx.say("key: ", k)
        end
        ngx.say("s = ", s)
    }
--- stream_response
key: B
key: f f
s = f+f=bar&B=foo
--- no_error_log
[error]
