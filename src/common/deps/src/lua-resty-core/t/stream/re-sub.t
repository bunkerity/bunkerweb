# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 8);

#no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sub, no submatch, no jit compile, regex cache
--- stream_server_config
    content_by_lua_block {
        local m, err
        local sub = ngx.re.sub
        for i = 1, 350 do
            s, n, err = sub("abcbd", "b", "B", "jo")
        end
        if not s then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end
        ngx.say("s: ", s)
        ngx.say("n: ", n)
    }
--- stream_response
s: aBcbd
n: 1
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
bad argument type
NYI



=== TEST 2: sub, no submatch, no jit compile, no regex cache
--- stream_server_config
    content_by_lua_block {
        local m, err
        local sub = ngx.re.sub
        for i = 1, 400 do
            s, n, err = sub("abcbd", "b", "B")
        end
        if not s then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end
        ngx.say("s: ", s)
        ngx.say("n: ", n)
    }
--- stream_response
s: aBcbd
n: 1
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
bad argument type



=== TEST 3: func + submatches
--- stream_server_config
    content_by_lua_block {
        local m, err
        local function f(m)
            return "[" .. m[0] .. "(" .. m[1] .. ")]"
        end
        local sub = ngx.re.sub
        for i = 1, 200 do
            s, n, err = sub("abcbd", "b(c)", f, "jo")
        end
        if not s then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end
        ngx.say("s: ", s)
        ngx.say("n: ", n)
    }
--- stream_response
s: a[bc(c)]bd
n: 1
--- no_error_log eval
[
"[error]",
"bad argument type",
qr/NYI (?!bytecode 51 at)/,
]



=== TEST 4: replace template + submatches
--- stream_server_config
    content_by_lua_block {
        local m, err
        local sub = ngx.re.sub
        for i = 1, 350 do
            s, n, err = sub("abcbd", "b(c)", "[$0($1)]", "jo")
        end
        if not s then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end
        ngx.say("s: ", s)
        ngx.say("n: ", n)
    }
--- stream_response
s: a[bc(c)]bd
n: 1
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/

--- no_error_log
[error]
bad argument type
NYI



=== TEST 5: replace template + submatches (exceeding buffers)
--- stream_server_config
    content_by_lua_block {
        local m, err
        local gsub = ngx.re.gsub
        local subj = string.rep("bcbd", 2048)
        for i = 1, 10 do
            s, n, err = gsub(subj, "b(c)", "[$0($1)]", "jo")
        end
        if not s then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end
        ngx.say("s: ", s)
        ngx.say("n: ", n)
    }
--- stream_response eval
"s: " . ("[bc(c)]bd" x 2048) .
"\nn: 2048\n"

--- no_error_log
[error]
bad argument type



=== TEST 6: ngx.re.gsub: use of resty.core's API in the user callback
--- stream_config
    lua_shared_dict dogs 12k;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        assert(dogs:set("foo", "bar"))

        local data = [[
            INNER
            INNER
]]

        local res =  ngx.re.gsub(data, "INNER", function(inner_matches)
            assert(dogs:get("foo"))
            return "INNER_REPLACED"
        end, "s")

        ngx.print(res)
    }
--- stream_response
            INNER_REPLACED
            INNER_REPLACED

--- no_error_log
[error]
bad argument type
NYI



=== TEST 7: ngx.re.gsub: recursive calling (github openresty/lua-nginx-module#445)
--- stream_server_config
    content_by_lua_block {
        function test()
            local data = [[
                OUTER {FIRST}
]]

            local p1 = "(OUTER)(.+)"
            local p2 = "{([A-Z]+)}"

            ngx.print(data)

            local res =  ngx.re.gsub(data, p1, function(m)
                -- ngx.say("pre: m[1]: [", m[1], "]")
                -- ngx.say("pre: m[2]: [", m[2], "]")

                local res = ngx.re.gsub(m[2], p2, function(_)
                    return "REPLACED"
                end, "")

                -- ngx.say("post: m[1]: [", m[1], "]")
                -- ngx.say("post m[2]: [", m[2], "]")
                return m[1] .. res
            end, "")

            ngx.print(res)
        end

        test()
    }
--- stream_response
                OUTER {FIRST}
                OUTER REPLACED
--- no_error_log
[error]
bad argument type
NYI



=== TEST 8: string replace subj is not a string type
--- stream_server_config
    content_by_lua_block {
        local newstr, n, err = ngx.re.sub(1234, "([0-9])[0-9]", 5, "jo")

        ngx.say(newstr)
    }
--- stream_response
534
--- no_error_log
[error]
attempt to get length of local 'subj' (a number value)



=== TEST 9: func replace return is not a string type (ngx.re.sub)
--- stream_server_config
    content_by_lua_block {
        local lookup = function(m)
            -- note we are returning a number type here
            return 5
        end

        local newstr, n, err = ngx.re.sub("hello, 1234", "([0-9])[0-9]", lookup, "jo")
        ngx.say(newstr)
    }
--- stream_response
hello, 534
--- no_error_log
[error]
attempt to get length of local 'bit' (a number value)



=== TEST 10: func replace return is not a string type (ngx.re.gsub)
--- stream_server_config
    content_by_lua_block {
        local lookup = function(m)
            -- note we are returning a number type here
            return 5
        end

        local newstr, n, err = ngx.re.gsub("hello, 1234", "([0-9])[0-9]", lookup, "jo")
        ngx.say(newstr)
    }
--- stream_response
hello, 55
--- no_error_log
[error]
attempt to get length of local 'bit' (a number value)
