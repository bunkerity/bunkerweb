# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 6);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: matched but w/o variables
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, world", "[a-z]+", "howdy", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
howdy, world
1



=== TEST 2: not matched
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, world", "[A-Z]+", "howdy", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, world
0



=== TEST 3: matched and with variables
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("a b c d", "(b) (c)", "[$0] [$1] [$2] [$3] [$134]", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
a [b c] [b] [c] [] [] d
1



=== TEST 4: matched and with named variables (bad template)
--- stream_server_config
    content_by_lua_block {
        local s, n, err = ngx.re.sub("a b c d",
                                     "(b) (c)",
                                     "[$0] [$1] [$2] [$3] [$hello]",
                                     "o")
        if s then
            ngx.say(s, ": ", n)

        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: failed to compile the replacement template
--- error_log
attempt to use named capturing variable "hello" (named captures not supported yet)



=== TEST 5: matched and with named variables (bracketed)
--- stream_server_config
    content_by_lua_block {
        local s, n, err = ngx.re.sub("a b c d",
                                     "(b) (c)",
                                     "[$0] [$1] [$2] [$3] [${hello}]",
                                     "o")
        if s then
            ngx.say(s, ": ", n)
        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: failed to compile the replacement template
--- error_log
attempt to use named capturing variable "hello" (named captures not supported yet)



=== TEST 6: matched and with bracketed variables
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("b c d", "(b) (c)", "[$0] [$1] [${2}] [$3] [${134}]", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
[b c] [b] [c] [] [] d
1



=== TEST 7: matched and with bracketed variables (unmatched brackets)
--- stream_server_config
    content_by_lua_block {
        local s, n, err = ngx.re.sub("b c d", "(b) (c)", "[$0] [$1] [${2}] [$3] [${134]", "o")
        if s then
            ngx.say(s, ": ", n)
        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: failed to compile the replacement template
--- error_log
the closing bracket in "134" variable is missing



=== TEST 8: matched and with bracketed variables (unmatched brackets)
--- stream_server_config
    content_by_lua_block {
        local s, n, err = ngx.re.sub("b c d", "(b) (c)", "[$0] [$1] [${2}] [$3] [${134", "o")
        if s then
            ngx.say(s, ": ", n)
        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: failed to compile the replacement template
--- error_log
the closing bracket in "134" variable is missing



=== TEST 9: matched and with bracketed variables (unmatched brackets)
--- stream_server_config
    content_by_lua_block {
        local s, n, err = ngx.re.sub("b c d", "(b) (c)", "[$0] [$1] [${2}] [$3] [${", "o")
        if s then
            ngx.say(s, ": ", n)
        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: failed to compile the replacement template
--- error_log
lua script: invalid capturing variable name found in "[$0] [$1] [${2}] [$3] [${"



=== TEST 10: trailing $
--- stream_server_config
    content_by_lua_block {
        local s, n, err = ngx.re.sub("b c d", "(b) (c)", "[$0] [$1] [${2}] [$3] [$", "o")
        if s then
            ngx.say(s, ": ", n)
        else
            ngx.say("error: ", err)
        end
    }
--- stream_response
error: failed to compile the replacement template
--- error_log
lua script: invalid capturing variable name found in "[$0] [$1] [${2}] [$3] [$"



=== TEST 11: matched but w/o variables and with literal $
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, world", "[a-z]+", "ho$$wdy", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
ho$wdy, world
1



=== TEST 12: non-anchored match
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", " [0-9] ", "x", "xo")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, x234
1



=== TEST 13: anchored match
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", "[0-9]", "x", "ao")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, 1234
0



=== TEST 14: function replace
--- stream_server_config
    content_by_lua_block {
        local repl = function (m)
            return "[" .. m[0] .. "] [" .. m[1] .. "]"
        end

        local s, n = ngx.re.sub("hello, 34", "([0-9])", repl, "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, [3] [3]4
1



=== TEST 15: function replace (failed)
--- stream_server_config
    content_by_lua_block {
        local repl = function (m)
            return "[" .. m[0] .. "] [" .. m[1] .. "]"
        end

        local s, n = ngx.re.sub("hello, 34", "([A-Z])", repl, "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, 34
0



=== TEST 16: bad repl arg type
--- SKIP
--- stream_server_config
    content_by_lua_block {
        local rc, s, n = pcall(ngx.re.sub, "hello, 34", "([A-Z])", true, "o")
        ngx.say(rc)
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
false
bad argument #3 to '?' (string, number, or function expected, got boolean)
nil



=== TEST 17: use number to replace
--- stream_server_config
    content_by_lua_block {
        local rc, s, n = pcall(ngx.re.sub, "hello, 34", "([0-9])", 72, "o")
        ngx.say(rc)
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
true
hello, 724
1



=== TEST 18: bad function return value type
--- SKIP
--- stream_server_config
    content_by_lua_block {
        local f = function (m) end
        local rc, s, n = pcall(ngx.re.sub, "hello, 34", "([0-9])", f, "o")
        ngx.say(rc)
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
false
bad argument #3 to '?' (string or number expected to be returned by the replace function, got nil)
nil



=== TEST 19: with regex cache (with text replace)
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", "([A-Z]+)", "baz", "io")
        ngx.say(s)
        ngx.say(n)

        local s, n = ngx.re.sub("howdy, 1234", "([A-Z]+)", "baz", "io")
        ngx.say(s)
        ngx.say(n)


        s, n = ngx.re.sub("1234, okay", "([A-Z]+)", "blah", "io")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("hi, 1234", "([A-Z]+)", "hello", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
baz, 1234
1
baz, 1234
1
1234, blah
1
hi, 1234
0



=== TEST 20: with regex cache (with func replace)
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", "([A-Z]+)", "baz", "io")
        ngx.say(s)
        ngx.say(n)

        local s, n = ngx.re.sub("howdy, 1234", "([A-Z]+)", function () return "bah" end, "io")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("1234, okay", "([A-Z]+)", function () return "blah" end, "io")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("hi, 1234", "([A-Z]+)", "hello", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
baz, 1234
1
bah, 1234
1
1234, blah
1
hi, 1234
0



=== TEST 21: exceeding regex cache max entries
--- stream_config
    lua_regex_cache_max_entries 2;
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", "([0-9]+)", "hello", "o")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("howdy, 567", "([0-9]+)", "hello", "oi")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("hiya, 98", "([0-9]+)", "hello", "ox")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, hello
1
howdy, hello
1
hiya, hello
1



=== TEST 22: disable regex cache completely
--- stream_config
    lua_regex_cache_max_entries 0;
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", "([0-9]+)", "hello", "o")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("howdy, 567", "([0-9]+)", "hello", "oi")
        ngx.say(s)
        ngx.say(n)

        s, n = ngx.re.sub("hiya, 98", "([0-9]+)", "hello", "ox")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, hello
1
howdy, hello
1
hiya, hello
1



=== TEST 23: empty replace
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("hello, 1234", "([0-9]+)", "", "o")
        ngx.say(s)
        ngx.say(n)

        local s, n = ngx.re.sub("hi, 5432", "([0-9]+)", "", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
hello, 
1
hi, 
1



=== TEST 24: matched and with variables w/o using named patterns in sub
--- stream_server_config
    content_by_lua_block {
        local s, n = ngx.re.sub("a b c d", "(?<first>b) (?<second>c)", "[$0] [$1] [$2] [$3] [$134]", "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
a [b c] [b] [c] [] [] d
1



=== TEST 25: matched and with variables using named patterns in func
--- stream_server_config
    error_log /tmp/nginx_error debug;
    content_by_lua_block {
        local repl = function (m)
            return "[" .. m[0] .. "] [" .. m["first"] .. "] [" .. m[2] .. "]"
        end

        local s, n = ngx.re.sub("a b c d", "(?<first>b) (?<second>c)", repl, "o")
        ngx.say(s)
        ngx.say(n)
    }
--- stream_response
a [b c] [b] [c] d
1
