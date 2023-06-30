# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 5);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: matched with j
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)", "j")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234
--- error_log
pcre JIT compiling result: 1



=== TEST 2: not matched with j
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, world", "([0-9]+)", "j")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
not matched!
--- error_log
pcre JIT compiling result: 1



=== TEST 3: matched with jo
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, 1234", "([0-9]+)", "jo")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
1234

--- grep_error_log eval
qr/pcre JIT compiling result: \d+/

--- grep_error_log_out eval
["pcre JIT compiling result: 1\n", ""]



=== TEST 4: not matched with jo
--- stream_server_config
    content_by_lua_block {
        m = ngx.re.match("hello, world", "([0-9]+)", "jo")
        if m then
            ngx.say(m[0])
        else
            ngx.say("not matched!")
        end
    }
--- stream_response
not matched!

--- grep_error_log eval
qr/pcre JIT compiling result: \d+/

--- grep_error_log_out eval
["pcre JIT compiling result: 1\n", ""]



=== TEST 5: bad pattern
--- stream_server_config
    content_by_lua_block {
        local m, err = ngx.re.match("hello\\nworld", "(abc", "j")
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



=== TEST 6: just hit match limit
--- stream_config
    lua_regex_match_limit 2940;
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files
>>> a.lua
local re = [==[(?i:([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:=|<=>|r?like|sounds\s+like|regexp)([\s'\"`´’‘\(\)]*)?\2|([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:!=|<=|>=|<>|<|>|\^|is\s+not|not\s+like|not\s+regexp)([\s'\"`´’‘\(\)]*)?(?!\6)([\d\w]+))]==]

s = string.rep([[ABCDEFG]], 21)

local start = ngx.now()

local res, err = ngx.re.match(s, re, "jo")

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



=== TEST 7: just not hit match limit
--- stream_config
    lua_regex_match_limit 2950;
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files
>>> a.lua
local re = [==[(?i:([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:=|<=>|r?like|sounds\s+like|regexp)([\s'\"`´’‘\(\)]*)?\2|([\s'\"`´’‘\(\)]*)?([\d\w]+)([\s'\"`´’‘\(\)]*)?(?:!=|<=|>=|<>|<|>|\^|is\s+not|not\s+like|not\s+regexp)([\s'\"`´’‘\(\)]*)?(?!\6)([\d\w]+))]==]

s = string.rep([[ABCDEFG]], 21)

local start = ngx.now()

local res, err = ngx.re.match(s, re, "jo")

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
