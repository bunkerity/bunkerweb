# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 5);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: gmatch matched
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("hello, halo", "h[a-z]|h[a-z][a-z]", "d") do
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
hel
hal



=== TEST 2: d + j
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("hello, halo", "h[a-z]|h[a-z][a-z]", "dj") do
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
hel
hal



=== TEST 3: fail to match
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[0-9]", "d")
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



=== TEST 4: gmatch matched but no iterate
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "d")
        ngx.say("done")
    }
--- stream_response
done



=== TEST 5: gmatch matched but only iterate once and still matches remain
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "d")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched")
        end
    }
--- stream_response
hello



=== TEST 6: gmatch matched + o
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("hello, world", "[a-z]+", "do") do
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



=== TEST 7: fail to match + o
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[0-9]", "do")
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



=== TEST 8: gmatch matched but no iterate + o
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "do")
        ngx.say("done")
    }
--- stream_response
done



=== TEST 9: gmatch matched but only iterate once and still matches remain + o
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+", "do")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched")
        end
    }
--- stream_response
hello



=== TEST 10: bad pattern
--- stream_server_config
    content_by_lua_block {
        local it, err = ngx.re.gmatch("hello\\nworld", "(abc", "d")
        if not it then
            ngx.say("error: ", err)
            return
        end
        ngx.say("success")
    }
--- stream_response
error: pcre_compile() failed: missing ) in "(abc"
--- no_error_log
[error]



=== TEST 11: UTF-8 mode without UTF-8 sequence checks
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("你好", ".", "Ud")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stap
probe process("$LIBPCRE_PATH").function("pcre_compile") {
    printf("compile opts: %x\n", $options)
}

probe process("$LIBPCRE_PATH").function("pcre_dfa_exec") {
    printf("exec opts: %x\n", $options)
}

--- stap_out
compile opts: 800
exec opts: 2000

--- stream_response
你
--- no_error_log
[error]



=== TEST 12: UTF-8 mode with UTF-8 sequence checks
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("你好", ".", "ud")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stap
probe process("$LIBPCRE_PATH").function("pcre_compile") {
    printf("compile opts: %x\n", $options)
}

probe process("$LIBPCRE_PATH").function("pcre_dfa_exec") {
    printf("exec opts: %x\n", $options)
}

--- stap_out
compile opts: 800
exec opts: 0

--- stream_response
你
--- no_error_log
[error]
