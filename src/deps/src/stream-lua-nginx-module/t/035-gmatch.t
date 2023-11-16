# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(5);

plan tests => repeat_each() * (blocks() * 2 + 7);

our $HtmlDir = html_dir;

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: gmatch
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("hello, world", "[a-z]+") do
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



=== TEST 2: fail to match
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[0-9]")
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



=== TEST 3: match but iterate more times (not just match at the end)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world!", "[a-z]+")
        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end
    }
--- stream_response
hello
world
nil
nil



=== TEST 4: match but iterate more times (just matched at the end)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+")
        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end

        local m = it()
        if m then ngx.say(m[0]) else ngx.say(m) end
    }
--- stream_response
hello
world
nil
nil



=== TEST 5: anchored match (failed)
--- stream_server_config
    content_by_lua_block {
        it = ngx.re.gmatch("hello, 1234", "([0-9]+)", "a")
        ngx.say(it())
    }
--- stream_response
nil



=== TEST 6: anchored match (succeeded)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("12 hello 34", "[0-9]", "a")
        local m = it()
        ngx.say(m[0])
        m = it()
        ngx.say(m[0])
        ngx.say(it())
    }
--- stream_response
1
2
nil



=== TEST 7: non-anchored gmatch (without regex cache)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("12 hello 34", "[0-9]")
        local m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
    }
--- stream_response
1
2
3
4
nil



=== TEST 8: non-anchored gmatch (with regex cache)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("12 hello 34", "[0-9]", "o")
        local m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
        m = it()
        ngx.say(m and m[0])
    }
--- stream_response
1
2
3
4
nil



=== TEST 9: anchored match (succeeded)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("12 hello 34", "[0-9]", "a")
        local m = it()
        ngx.say(m[0])
        m = it()
        ngx.say(m[0])
        ngx.say(it())
    }
--- stream_response
1
2
nil



=== TEST 10: gmatch (look-behind assertion)
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("{foobar}, {foobaz}", "(?<=foo)ba[rz]") do
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
bar
baz



=== TEST 11: gmatch (look-behind assertion 2)
--- stream_server_config
    content_by_lua_block {
        for m in ngx.re.gmatch("{foobarbaz}", "(?<=foo)bar|(?<=bar)baz") do
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
bar
baz



=== TEST 12: with regex cache
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, 1234", "([A-Z]+)", "io")
        local m = it()
        ngx.say(m and m[0])

        it = ngx.re.gmatch("1234, okay", "([A-Z]+)", "io")
        m = it()
        ngx.say(m and m[0])

        it = ngx.re.gmatch("hi, 1234", "([A-Z]+)", "o")
        m = it()
        ngx.say(m and m[0])
    }
--- stap2
F(ngx_http_lua_ngx_re_gmatch_iterator) { println("iterator") }
F(ngx_http_lua_ngx_re_gmatch_gc) { println("gc") }
F(ngx_http_lua_ngx_re_gmatch_cleanup) { println("cleanup") }
--- stream_response
hello
okay
nil



=== TEST 13: exceeding regex cache max entries
--- stream_config
    lua_regex_cache_max_entries 2;
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, 1234", "([0-9]+)", "o")
        local m = it()
        ngx.say(m and m[0])

        it = ngx.re.gmatch("howdy, 567", "([0-9]+)", "oi")
        m = it()
        ngx.say(m and m[0])

        it = ngx.re.gmatch("hiya, 98", "([0-9]+)", "ox")
        m = it()
        ngx.say(m and m[0])
    }
--- stream_response
1234
567
98



=== TEST 14: disable regex cache completely
--- stream_config
    lua_regex_cache_max_entries 0;
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, 1234", "([0-9]+)", "o")
        local m = it()
        ngx.say(m and m[0])

        it = ngx.re.gmatch("howdy, 567", "([0-9]+)", "oi")
        local m = it()
        ngx.say(m and m[0])

        it = ngx.re.gmatch("hiya, 98", "([0-9]+)", "ox")
        local m = it()
        ngx.say(m and m[0])
    }
--- stream_response
1234
567
98



=== TEST 15: gmatch matched but no iterate
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+")
        ngx.say("done")
    }
--- stream_response
done



=== TEST 16: gmatch matched but only iterate once and still matches remain
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, world", "[a-z]+")
        local m = it()
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched")
        end
    }
--- stream_response
hello



=== TEST 17: gmatch matched but no iterate and early forced GC
--- stream_server_config
    content_by_lua_block {
        local a = {}
        for i = 1, 3 do
            it = ngx.re.gmatch("hello, world", "[a-z]+")
            it()
            collectgarbage()
            table.insert(a, {"hello", "world"})
        end
        ngx.say("done")
    }
--- stream_response
done



=== TEST 18: gmatch iterator used by another request
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;;';"
--- stream_server_config
    content_by_lua_block {
    package.loaded.foo = nil
    collectgarbage()
    local foo = require "foo"
    local m = foo.go()
    ngx.say(m and "matched" or "no")
    }
--- stream_server_config2
    content_by_lua_block {
    local foo = require "foo"
    local m = foo.go()
    ngx.say(m and "matched" or "no")
    }
--- user_files
>>> foo.lua
module("foo", package.seeall)

local it

function go()
    if not it then
        it = ngx.re.gmatch("hello, world", "[a-z]+")
    end

    return it()
end
--- stream_response
matched
matched
--- no_error_log
[error]



=== TEST 19: gmatch (empty matched string)
--- stream_server_config
    content_by_lua_block {
    for m in ngx.re.gmatch("hello", "a|") do
        if m then
            ngx.say("matched: [", m[0], "]")
        else
            ngx.say("not matched: ", m)
        end
    end
    }
--- stream_response
matched: []
matched: []
matched: []
matched: []
matched: []
matched: []



=== TEST 20: gmatch with named pattern
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("1234, 1234", "(?<first>[0-9]+)")
        m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m["first"])
        else
            ngx.say("not matched!")
        end

        m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m["first"])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
1234
1234
1234
1234
1234



=== TEST 21: gmatch with multiple named pattern
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("1234, abcd, 1234", "(?<first>[0-9]+)|(?<second>[a-z]+)")

        m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
            ngx.say(m["first"])
            ngx.say(m["second"])
        else
            ngx.say("not matched!")
        end

        m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
            ngx.say(m["first"])
            ngx.say(m["second"])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
1234
false
1234
false
abcd
false
abcd
false
abcd



=== TEST 22: gmatch with duplicate named pattern w/ extraction
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("hello, 1234", "(?<first>[a-z]+), (?<first>[0-9]+)", "D")
        m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
            ngx.say(table.concat(m.first,"-"))
        else
            ngx.say("not matched!")
        end

        m = it()
        if m then
         ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
            ngx.say(table.concat(m.first,"-"))
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
hello, 1234
hello
1234
hello-1234
not matched!



=== TEST 23: named captures are empty
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("1234", "(?<first>[a-z]*)([0-9]+)", "")
        local m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m.first)
            ngx.say(m[1])
            ngx.say(m[2])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234


1234



=== TEST 24: named captures are empty (with regex cache)
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("1234", "(?<first>[a-z]*)([0-9]+)", "o")
        local m = it()
        if m then
            ngx.say(m[0])
            ngx.say(m.first)
            ngx.say(m[1])
            ngx.say(m[2])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234


1234



=== TEST 25: bad pattern
--- stream_server_config
    content_by_lua_block {
        local it, err = ngx.re.gmatch("hello\nworld", "(abc")
        if not err then
            ngx.say("good")

        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: pcre_compile() failed: missing ) in "(abc"
--- no_error_log
[error]



=== TEST 26: bad UTF-8
--- stream_server_config
    content_by_lua_block {
        local target = "你好"
        local regex = "你好"

        -- Note the D here
        local it, err = ngx.re.gmatch(string.sub(target, 1, 4), regex, "u")

        if err then
            ngx.say("error: ", err)
            return
        end

        local m, err = it()
        if err then
            ngx.say("error: ", err)
            return
        end

        if m then
            ngx.say("matched: ", m[0])
        else
            ngx.say("not matched")
        end
    }
--- stream_response_like chop
error: pcre_exec\(\) failed: -10

--- no_error_log
[error]



=== TEST 27: UTF-8 mode without UTF-8 sequence checks
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("你好", ".", "U")
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

probe process("$LIBPCRE_PATH").function("pcre_exec") {
    printf("exec opts: %x\n", $options)
}

--- stap_out
compile opts: 800
exec opts: 2000

--- stream_response
你
--- no_error_log
[error]



=== TEST 28: UTF-8 mode with UTF-8 sequence checks
--- stream_server_config
    content_by_lua_block {
        local it = ngx.re.gmatch("你好", ".", "u")
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

probe process("$LIBPCRE_PATH").function("pcre_exec") {
    printf("exec opts: %x\n", $options)
}

--- stap_out
compile opts: 800
exec opts: 0

--- stream_response
你
--- no_error_log
[error]



=== TEST 29: just hit match limit
--- stream_config
    lua_regex_match_limit 5000;
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files
>>> a.lua
local re = [==[(?i:([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:=|<=>|r?like|sounds\s+like|regexp)([\s'\"`´’‘\(\)]*)?\2|([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:!=|<=|>=|<>|<|>|\^|is\s+not|not\s+like|not\s+regexp)([\s'\"`´’‘\(\)]*)?(?!\6)([\d\w]+))]==]

s = string.rep([[ABCDEFG]], 10)

local start = ngx.now()

local it, err = ngx.re.gmatch(s, re, "o")
if not it then
    ngx.say("failed to gen iterator: ", err)
    return
end

local res, err = it()

--[[
ngx.update_time()
local elapsed = ngx.now() - start
ngx.say(elapsed, " sec elapsed.")
]]

if not res then
    if err then
        ngx.say("error: ", err)
        return
    end
    ngx.say("failed to match")
    return
end

--- stream_response
error: pcre_exec() failed: -8



=== TEST 30: just not hit match limit
--- stream_config
    lua_regex_match_limit 5700;
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files
>>> a.lua
local re = [==[(?i:([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:=|<=>|r?like|sounds\s+like|regexp)([\s'\"`´’‘\(\)]*)?\2|([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:!=|<=|>=|<>|<|>|\^|is\s+not|not\s+like|not\s+regexp)([\s'\"`´’‘\(\)]*)?(?!\6)([\d\w]+))]==]

s = string.rep([[ABCDEFG]], 10)

local start = ngx.now()

local it, err = ngx.re.gmatch(s, re, "o")
if not it then
    ngx.say("failed to gen iterator: ", err)
    return
end

res, err = it()

--[[
ngx.update_time()
local elapsed = ngx.now() - start
ngx.say(elapsed, " sec elapsed.")
]]

if not res then
    if err then
        ngx.say("error: ", err)
        return
    end
    ngx.say("failed to match")
    return
end

--- stream_response
failed to match
