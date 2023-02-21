# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 1);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)", "o")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234



=== TEST 2: escaping sequences
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "(\\d+)", "o")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234



=== TEST 3: single capture
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]{2})[0-9]+", "o")
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



=== TEST 4: multiple captures
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



=== TEST 5: not matched
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "foo", "o")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
not matched: nil



=== TEST 6: case sensitive by default
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "HELLO", "o")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
not matched: nil



=== TEST 7: case sensitive by default
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "HELLO", "oi")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello



=== TEST 8: UTF-8 mode
--- stream_server_config
    content_by_lua_block {
        local rc, m = pcall(ngx.re.match, "hello章亦春", "HELLO.{2}", "iou")
        if not rc then
            ngx.say("error: ", m)
            return
        end
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response_like chop
this version of PCRE is not compiled with PCRE_UTF8 support|^hello章亦$



=== TEST 9: multi-line mode (^ at line head)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", "^world", "mo")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
world



=== TEST 10: multi-line mode (. does not match \n)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", ".*", "om")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello



=== TEST 11: single-line mode (^ as normal)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", "^world", "so")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
not matched: nil



=== TEST 12: single-line mode (dot all)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", ".*", "os")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
hello
world



=== TEST 13: extended mode (ignore whitespaces)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello\nworld", [[\w     \w]], "xo")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched: ", m)
        end
    }
--- stream_response
he



=== TEST 14: bad pattern
--- stream_server_config
    content_by_lua_block {
        local m, err = ngx.re.match("hello\\nworld", "(abc", "o")
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



=== TEST 15: bad option
--- stream_server_config
    content_by_lua_block {
        rc, m = pcall(ngx.re.match, "hello\\nworld", ".*", "Ho")
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
^error: .*?unknown flag "H"



=== TEST 16: extended mode (ignore whitespaces)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, world", "(world)|(hello)", "xo")
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



=== TEST 17: optional trailing captures
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)(h?)", "o")
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



=== TEST 18: anchored match (failed)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)", "oa")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
not matched!



=== TEST 19: anchored match (succeeded)
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("1234, hello", "([0-9]+)", "ao")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234



=== TEST 20: match with ctx but no pos
--- stream_server_config
    content_by_lua_block {
        local ctx = {}
        m = ngx.re.match("1234, hello", "([0-9]+)", "o", ctx)
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



=== TEST 21: match with ctx and a pos
--- stream_server_config
    content_by_lua_block {
        local ctx = { pos = 3 }
        m = ngx.re.match("1234, hello", "([0-9]+)", "o", ctx)
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



=== TEST 22: match (look-behind assertion)
--- stream_server_config
    content_by_lua_block {
        local ctx = {}
        local m = ngx.re.match("{foobarbaz}", "(?<=foo)bar|(?<=bar)baz", "o", ctx)
        ngx.say(m and m[0])

        m = ngx.re.match("{foobarbaz}", "(?<=foo)bar|(?<=bar)baz", "o", ctx)
        ngx.say(m and m[0])
    }
--- stream_response
bar
baz



=== TEST 23: match (with regex cache)
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "([A-Z]+)", "io")
        ngx.say(m and m[0])

        m = ngx.re.match("1234, okay", "([A-Z]+)", "io")
        ngx.say(m and m[0])

        m = ngx.re.match("hello, 1234", "([A-Z]+)", "o")
        ngx.say(m and m[0])
    }
--- stream_response
hello
okay
nil



=== TEST 24: match (with regex cache and ctx)
--- stream_server_config
    content_by_lua_block {
        local ctx = {}
        local m = ngx.re.match("hello, 1234", "([A-Z]+)", "io", ctx)
        ngx.say(m and m[0])
        ngx.say(ctx.pos)

        m = ngx.re.match("1234, okay", "([A-Z]+)", "io", ctx)
        ngx.say(m and m[0])
        ngx.say(ctx.pos)

        ctx.pos = 1
        m = ngx.re.match("hi, 1234", "([A-Z]+)", "o", ctx)
        ngx.say(m and m[0])
        ngx.say(ctx.pos)
    }
--- stream_response
hello
6
okay
11
nil
1



=== TEST 25: exceeding regex cache max entries
--- stream_config
    lua_regex_cache_max_entries 2;
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "([0-9]+)", "o")
        ngx.say(m and m[0])

        m = ngx.re.match("howdy, 567", "([0-9]+)", "oi")
        ngx.say(m and m[0])

        m = ngx.re.match("hiya, 98", "([0-9]+)", "ox")
        ngx.say(m and m[0])
    }
--- stream_response
1234
567
98



=== TEST 26: disable regex cache completely
--- stream_config
    lua_regex_cache_max_entries 0;
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "([0-9]+)", "o")
        ngx.say(m and m[0])

        m = ngx.re.match("howdy, 567", "([0-9]+)", "oi")
        ngx.say(m and m[0])

        m = ngx.re.match("hiya, 98", "([0-9]+)", "ox")
        ngx.say(m and m[0])
    }
--- stream_response
1234
567
98



=== TEST 27: named subpatterns w/ extraction
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "(?<first>[a-z]+), [0-9]+", "o")
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



=== TEST 28: duplicate named subpatterns w/ extraction
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, 1234", "(?<first>[a-z]+), (?<first>[0-9]+)", "Do")
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



=== TEST 29: named captures are empty strings
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("1234", "(?<first>[a-z]*)([0-9]+)", "o")
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



=== TEST 30: named captures are nil
--- stream_server_config
    content_by_lua_block {
        local m = ngx.re.match("hello, world", "(world)|(hello)|(?<named>howdy)", "o")
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
