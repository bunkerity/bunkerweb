# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 9);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: gmatch matched
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("hello, world", "[a-z]+", "j") do
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
hello
world
--- error_log
pcre JIT compiling result: 1



=== TEST 2: fail to match
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[0-9]", "j")
        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end
    }
--- stream_response
nil
nil
nil
--- error_log
pcre JIT compiling result: 1



=== TEST 3: gmatch matched but no iterate
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "j")
        ngx.say("done")
    }
--- stream_response
done
--- error_log
pcre JIT compiling result: 1



=== TEST 4: gmatch matched but only iterate once and still matches remain
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "j")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched")
        end
    }
--- stream_response
hello
--- error_log
pcre JIT compiling result: 1



=== TEST 5: gmatch matched + o
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("hello, world", "[a-z]+", "jo") do
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
hello
world

--- grep_error_log eval
qr/pcre JIT compiling result: \d+/

--- grep_error_log_out eval
["pcre JIT compiling result: 1\n", ""]



=== TEST 6: fail to match + o
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[0-9]", "jo")
        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end
    }
--- stream_response
nil
nil
nil

--- grep_error_log eval
qr/pcre JIT compiling result: \d+/

--- grep_error_log_out eval
["pcre JIT compiling result: 1\n", ""]



=== TEST 7: gmatch matched but no iterate + o
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "jo")
        ngx.say("done")
    }
--- stream_response
done

--- grep_error_log eval
qr/pcre JIT compiling result: \d+/

--- grep_error_log_out eval
["pcre JIT compiling result: 1\n", ""]



=== TEST 8: gmatch matched but only iterate once and still matches remain + o
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "jo")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched")
        end
    }
--- stream_response
hello

--- grep_error_log eval
qr/pcre JIT compiling result: \d+/

--- grep_error_log_out eval
["pcre JIT compiling result: 1\n", ""]



=== TEST 9: bad pattern
--- stream_server_config
    content_by_lua_block {
        local m, err = ngx.re.gmatch("hello\\nworld", "(abc", "j")
        if not m then
            ngx.say("error: ", err)
            return
        end
        ngx.say("success")
    }
--- stream_response
error: pcre_compile() failed: missing ) in "(abc"
--- no_error_log
[error]
