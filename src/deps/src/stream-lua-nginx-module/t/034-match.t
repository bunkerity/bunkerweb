# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- no_error_log
[error]



=== TEST 2: escaping sequences
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", [[(\d+)]])
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- no_error_log
[error]



=== TEST 3: single capture
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]{2})[0-9]+")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
12
--- no_error_log
[error]



=== TEST 4: multiple captures
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([a-z]+).*?([0-9]{2})[0-9]+", "")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
hello, 1234
hello
12
--- no_error_log
[error]



=== TEST 5: multiple captures (with o)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([a-z]+).*?([0-9]{2})[0-9]+", "o")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
hello, 1234
hello
12
--- no_error_log
[error]



=== TEST 6: not matched
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "foo")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
not matched: nil
--- no_error_log
[error]



=== TEST 7: case sensitive by default
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "HELLO")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
not matched: nil
--- no_error_log
[error]



=== TEST 8: case insensitive
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "HELLO", "i")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello
--- no_error_log
[error]



=== TEST 9: UTF-8 mode
--- stream_server_config
    content_by_lua_block {
        rc, err = pcall(ngx.re.match, "hello章亦春", "HELLO.{2}", "iu")
        if not rc then
            ngx.say("FAIL: ", err)
            return
        end
        local m = err
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response_like chop
^(?:FAIL: bad argument \#2 to '\?' \(pcre_compile\(\) failed: this version of PCRE is not compiled with PCRE_UTF8 support in "HELLO\.\{2\}" at "HELLO\.\{2\}"\)|hello章亦)$
--- no_error_log
[error]



=== TEST 10: multi-line mode (^ at line head)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", "^world", "m")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
world
--- no_error_log
[error]



=== TEST 11: multi-line mode (. does not match \n)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", ".*", "m")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello
--- no_error_log
[error]



=== TEST 12: single-line mode (^ as normal)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", "^world", "s")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
not matched: nil
--- no_error_log
[error]



=== TEST 13: single-line mode (dot all)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", ".*", "s")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello
world
--- no_error_log
[error]



=== TEST 14: extended mode (ignore whitespaces)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", [[\w     \w]], "x")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
he
--- no_error_log
[error]



=== TEST 15: bad pattern
--- stream_server_config
    content_by_lua_block {
        local m, err = ngx.re.match("hello\nworld", "(abc")
        if m then
            ngx.say(m[0])

        else
            if err then
                ngx.say("error: ", err)

            else
                ngx.say("not matched: ", m)
            end
        end
    }
--- stream_response
error: pcre_compile() failed: missing ) in "(abc"
--- no_error_log
[error]



=== TEST 16: bad option
--- stream_server_config
    content_by_lua_block {
        rc, m = pcall(ngx.re.match, "hello\nworld", ".*", "Hm")
        if rc then
            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched: ", m)
            end
        else
            ngx.say("error: ", m)
        end
    }
--- stream_response_like chop
error: .*?unknown flag "H" \(flags "Hm"\)



=== TEST 17: extended mode (ignore whitespaces)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, world", "(world)|(hello)", "x")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello
false
hello
--- no_error_log
[error]



=== TEST 18: optional trailing captures
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)(h?)")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response eval
"1234
1234

"
--- no_error_log
[error]



=== TEST 19: anchored match (failed)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)", "a")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
not matched!
--- no_error_log
[error]



=== TEST 20: anchored match (succeeded)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("1234, hello", "([0-9]+)", "a")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- no_error_log
[error]



=== TEST 21: match with ctx but no pos
--- stream_server_config
    content_by_lua_block {
        local ctx = {}
        m = ngx.re.match("1234, hello", "([0-9]+)", "", ctx)
        if m then
            ngx.say(m[0])
            ngx.say(ctx.pos)
        else
            ngx.say("not matched!")
            ngx.say(ctx.pos)
        end
    }
--- stream_response
1234
5
--- no_error_log
[error]



=== TEST 22: match with ctx and a pos
--- stream_server_config
    content_by_lua_block {
        local ctx = { pos = 3 }
        m = ngx.re.match("1234, hello", "([0-9]+)", "", ctx)
        if m then
            ngx.say(m[0])
            ngx.say(ctx.pos)
        else
            ngx.say("not matched!")
            ngx.say(ctx.pos)
        end
    }
--- stream_response
34
5
--- no_error_log
[error]



=== TEST 23: match (look-behind assertion)
--- stream_server_config
    content_by_lua_block {
        local ctx = {}
        local m = ngx.re.match("{foobarbaz}", "(?<=foo)bar|(?<=bar)baz", "", ctx)
        ngx.say(m and m[0])

        m = ngx.re.match("{foobarbaz}", "(?<=foo)bar|(?<=bar)baz", "", ctx)
        ngx.say(m and m[0])
    }
--- stream_response
bar
baz
--- no_error_log
[error]



=== TEST 24: escaping sequences
--- stream_server_config
    content_by_lua_file html/a.lua;
--- user_files
>>> a.lua
local uri = "<impact>2</impact>"
local regex = '(?:>[\\w\\s]*</?\\w{2,}>)';
ngx.say("regex: ", regex)
m = ngx.re.match(uri, regex, "oi")
if m then
    ngx.say("[", m[0], "]")
else
    ngx.say("not matched!")
end
--- stream_response
regex: (?:>[\w\s]*</?\w{2,}>)
[>2</impact>]
--- no_error_log
[error]



=== TEST 25: long brackets
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", [[\d+]])
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- no_error_log
[error]



=== TEST 26: bad pattern
--- stream_server_config
    content_by_lua_block {
        local m, err = ngx.re.match("hello, 1234", "([0-9]+")
        if m then
            ngx.say(m[0])

        else
            if err then
                ngx.say("error: ", err)

            else
                ngx.say("not matched!")
            end
        end
    }
--- stream_response
error: pcre_compile() failed: missing ) in "([0-9]+"

--- no_error_log
[error]



=== TEST 27: long brackets containing [...]
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", [[([0-9]+)]])
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- no_error_log
[error]



=== TEST 28: bug report (github issue #72)
--- stream_server_config
    content_by_lua_block {
        local m, err = ngx.re.match("hello", "hello", "j")
        ngx.say("done: ", m and "yes" or "no")
    }
--- stream_server_config2
    content_by_lua_block {
        ngx.re.match("hello", "world", "j")
        ngx.say("done: ", m and "yes" or "no")
    }
--- stream_response
done: yes
done: no
--- no_error_log
[error]



=== TEST 29: non-empty subject, empty pattern
--- stream_server_config
    content_by_lua_block {
        local ctx = {}
        local m = ngx.re.match("hello, 1234", "", "", ctx)
        if m then
            ngx.say("pos: ", ctx.pos)
            ngx.say("m: ", m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
pos: 1
m: 
--- no_error_log
[error]



=== TEST 30: named subpatterns w/ extraction
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "(?<first>[a-z]+), [0-9]+")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m.first)
            ngx.say(m.second)
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
hello, 1234
hello
hello
nil
--- no_error_log
[error]



=== TEST 31: duplicate named subpatterns w/ extraction
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "(?<first>[a-z]+), (?<first>[0-9]+)", "D")
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
--- no_error_log
[error]



=== TEST 32: named captures are empty strings
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("1234", "(?<first>[a-z]*)([0-9]+)")
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
--- no_error_log
[error]



=== TEST 33: named captures are nil
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, world", "(world)|(hello)|(?<named>howdy)")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
            ngx.say(m[3])
            ngx.say(m["named"])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
hello
false
hello
false
false
--- no_error_log
[error]



=== TEST 34: duplicate named subpatterns
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, world",
                               [[(?<named>\w+), (?<named>\w+)]],
                               "D")
        if m then
            ngx.say(m[0])
            ngx.say(m[1])
            ngx.say(m[2])
            ngx.say(table.concat(m.named,"-"))
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
hello, world
hello
world
hello-world
--- no_error_log
[error]



=== TEST 35: Javascript compatible mode
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("章", [[\u7AE0]], "uJ")
        if m then
            ngx.say("matched: ", m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
matched: 章
--- no_error_log
[error]



=== TEST 36: empty duplicate captures
--- stream_server_config
    content_by_lua_block {
        local target = 'test'
        local regex = '^(?:(?<group1>(?:foo))|(?<group2>(?:bar))|(?<group3>(?:test)))$'

        -- Note the D here
        local m = ngx.re.match(target, regex, 'D')

        ngx.say(type(m.group1))
        ngx.say(type(m.group2))
    }
--- stream_response
nil
nil
--- no_error_log
[error]



=== TEST 37: bad UTF-8
--- stream_server_config
    content_by_lua_block {
        local target = "你好"
        local regex = "你好"

        -- Note the D here
        local m, err = ngx.re.match(string.sub(target, 1, 4), regex, "u")

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
^error: pcre_exec\(\) failed: -10$

--- no_error_log
[error]



=== TEST 38: UTF-8 mode without UTF-8 sequence checks
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("你好", ".", "U")
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



=== TEST 39: UTF-8 mode with UTF-8 sequence checks
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("你好", ".", "u")
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



=== TEST 40: just hit match limit
--- stream_config
    lua_regex_match_limit 5000;
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files
>>> a.lua
local re = [==[(?i:([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:=|<=>|r?like|sounds\s+like|regexp)([\s'\"`´’‘\(\)]*)?\2|([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:!=|<=|>=|<>|<|>|\^|is\s+not|not\s+like|not\s+regexp)([\s'\"`´’‘\(\)]*)?(?!\6)([\d\w]+))]==]

s = string.rep([[ABCDEFG]], 10)

local start = ngx.now()

local res, err = ngx.re.match(s, re, "o")

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



=== TEST 41: just not hit match limit
--- stream_config
    lua_regex_match_limit 5700;
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files
>>> a.lua
local re = [==[(?i:([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:=|<=>|r?like|sounds\s+like|regexp)([\s'\"`´’‘\(\)]*)?\2|([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:!=|<=|>=|<>|<|>|\^|is\s+not|not\s+like|not\s+regexp)([\s'\"`´’‘\(\)]*)?(?!\6)([\d\w]+))]==]

s = string.rep([[ABCDEFG]], 10)

local start = ngx.now()

local res, err = ngx.re.match(s, re, "o")

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
--- no_error_log
[error]



=== TEST 42: extra table argument
--- stream_server_config
    content_by_lua_block {
        local res = {}
        local s = "hello, 1234"
        m = ngx.re.match(s, [[(\d)(\d)]], "o", nil, res)
        if m then
            ngx.say("1: m size: ", #m)
            ngx.say("1: res size: ", #res)
        else
            ngx.say("1: not matched!")
        end
        m = ngx.re.match(s, [[(\d)]], "o", nil, res)
        if m then
            ngx.say("2: m size: ", #m)
            ngx.say("2: res size: ", #res)
        else
            ngx.say("2: not matched!")
        end
    }
--- stream_response
1: m size: 2
1: res size: 2
2: m size: 2
2: res size: 2
--- no_error_log
[error]



=== TEST 43: init_by_lua
--- stream_config
    init_by_lua_block {
        m = ngx.re.match("hello, 1234", [[(\d+)]])
--- stream_server_config
    content_by_lua_block {
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- no_error_log
[error]
--- SKIP
