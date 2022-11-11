# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5 + 1);

#no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: matched, no submatch, no jit compile, no regex cache
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 400 do
                m, err = match("a", "a")
            end
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end
            if not m then
                ngx.log(ngx.ERR, "no match")
                return
            end
            ngx.say("matched: ", m[0])
            ngx.say("$1: ", m[1])
            -- ngx.say("$2: ", m[2])
            -- ngx.say("$3: ", m[3])
            -- collectgarbage()
        }
    }
--- request
GET /re
--- response_body
matched: a
$1: nil
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
bad argument type



=== TEST 2: matched, no submatch, jit compile, regex cache
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 400 do
                m, err = match("a", "a", "jo")
            end
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end
            if not m then
                ngx.log(ngx.ERR, "no match")
                return
            end
            ngx.say("matched: ", m[0])
            ngx.say("$1: ", m[1])
            -- collectgarbage()
        }
    }
--- request
GET /re
--- response_body
matched: a
$1: nil
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
NYI



=== TEST 3: not matched, no submatch, jit compile, regex cache
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 200 do
                m, err = match("b", "a", "jo")
            end
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end
            if not m then
                ngx.say("no match")
                return
            end
            ngx.say("matched: ", m[0])
            ngx.say("$1: ", m[1])
            -- collectgarbage()
        }
    }
--- request
GET /re
--- response_body
no match
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]



=== TEST 4: not matched, no submatch, no jit compile, no regex cache
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 100 do
                m, err = match("b", "a")
            end
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end
            if not m then
                ngx.say("no match")
                return
            end
            ngx.say("matched: ", m[0])
            ngx.say("$1: ", m[1])
            -- collectgarbage()
        }
    }
--- request
GET /re
--- response_body
no match
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
bad argument type



=== TEST 5: submatches, matched, no regex cache
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 100 do
                m, err = match("hello, 1234", [[(\d)(\d+)]])
            end
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end
            if not m then
                ngx.log(ngx.ERR, "no match")
                return
            end
            ngx.say("matched: ", m[0])
            ngx.say("$1: ", m[1])
            ngx.say("$2: ", m[2])
            ngx.say("$3: ", m[3])
            -- collectgarbage()
        }
    }
--- request
GET /re
--- response_body
matched: 1234
$1: 1
$2: 234
$3: nil
--- no_error_log
[error]
bad argument type
NYI



=== TEST 6: submatches, matched, with regex cache
--- config
    location = /re {
        access_log off;
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 100 do
                m, err = match("hello, 1234", [[(\d)(\d+)]], "jo")
            end
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end
            if not m then
                ngx.log(ngx.ERR, "no match")
                return
            end
            ngx.say("matched: ", m[0])
            ngx.say("$1: ", m[1])
            ngx.say("$2: ", m[2])
            ngx.say("$3: ", m[3])
            -- ngx.say(table.maxn(m))
            -- collectgarbage()
        }
    }
--- request
GET /re
--- response_body
matched: 1234
$1: 1
$2: 234
$3: nil
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
bad argument type
NYI



=== TEST 7: named subpatterns w/ extraction (matched)
--- config
    location /re {
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 100 do
                m, err = match("hello, 1234", "(?<first>[a-z]+), [0-9]+", "jo")
            end
            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m.first)
                ngx.say(m.second)
            else
                if err then
                    ngx.say("error: ", err)
                    return
                end
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
hello, 1234
hello
hello
nil

--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
bad argument type
NYI



=== TEST 8: named subpatterns w/ extraction (use of duplicate names in non-duplicate mode)
--- config
    location /re {
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 200 do
                m, err = match("hello, 1234", "(?<first>[a-z])(?<first>[a-z]+), [0-9]+", "jo")
            end
            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m.first)
                ngx.say(m.second)
            else
                if err then
                    ngx.say("error: ", err)
                    return
                end
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body_like chop
error: pcre_compile\(\) failed: two named subpatterns have the same name

--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
bad argument type
NYI



=== TEST 9: named subpatterns w/ extraction (use of duplicate names in duplicate mode)
--- config
    location /re {
        content_by_lua_block {
            local m, err
            local match = ngx.re.match
            for i = 1, 100 do
                m, err = match("hello, 1234", "(?<first>[a-z])(?<first>[a-z]+), [0-9]+", "joD")
                m, err = match("hello, 1234", "(?<first>[a-z])(?<first>[a-z]+), [0-9]+", "joD")
                m, err = match("hello, 1234", "(?<first>[a-z])(?<first>[a-z]+), [0-9]+", "joD")
                m, err = match("hello, 1234", "(?<first>[a-z])(?<first>[a-z]+), [0-9]+", "joD")
                m, err = match("hello, 1234", "(?<first>[a-z])(?<first>[a-z]+), [0-9]+", "joD")
            end
            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m[2])
                ngx.say(table.concat(m.first, "|"))
                ngx.say(m.second)
            else
                if err then
                    ngx.say("error: ", err)
                    return
                end
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body_like
hello, 1234
h
ello
h|ello
nil

--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
bad argument type
NYI



=== TEST 10: captures input table in ngx.re.match
--- config
    location /re {
        content_by_lua_block {
            local new_tab = require "table.new"
            local clear_tab = require "table.clear"
            local m
            local res = new_tab(5, 0)
            res[5] = "hello"
            for i = 1, 100 do
                m = ngx.re.match("hello, 1234", "([0-9])([0-9])([0-9])([0-9])", "jo", nil, res)
            end

            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m[2])
                ngx.say(m[3])
                ngx.say(m[4])
                ngx.say(m[5])
            else
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
1234
1
2
3
4
hello
--- no_error_log
[error]
NYI
--- error_log eval
qr/\[TRACE\s+\d+\s+/



=== TEST 11: unmatched captures are false
--- config
    location /re {
        content_by_lua_block {
            local m = ngx.re.match("hello!", "(hello)(, .+)?(!)", "jo")

            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m[2])
                ngx.say(m[3])
            else
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
hello!
hello
false
!
--- no_error_log
[error]
NYI
--- error_log eval
qr/\[TRACE\s+\d+\s+/



=== TEST 12: unmatched trailing captures are false
--- config
    location /re {
        content_by_lua_block {
            local m = ngx.re.match("hello", "(hello)(, .+)?(!)?", "jo")

            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m[2])
                ngx.say(m[3])
            else
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
hello
hello
false
false
--- no_error_log
[error]
NYI
--- error_log eval
qr/\[TRACE\s+\d+\s+/



=== TEST 13: unmatched named captures are false
--- config
    location /re {
        content_by_lua_block {
            local m = ngx.re.match("hello!", "(?<first>hello)(?<second>, .+)?(?<third>!)", "jo")

            if m then
                ngx.say(m[0])
                ngx.say(m[1])
                ngx.say(m[2])
                ngx.say(m[3])
                ngx.say(m.first)
                ngx.say(m.second)
                ngx.say(m.third)
            else
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
hello!
hello
false
!
hello
false
!
--- no_error_log
[error]
NYI
--- error_log eval
qr/\[TRACE\s+\d+\s+/



=== TEST 14: subject is not a string type
--- config
    location /re {
        content_by_lua_block {
            local m = ngx.re.match(12345, [=[(\d+)]=], "jo")

            if m then
                ngx.say(m[0])
                ngx.say(m[1])
            else
                ngx.say("not matched")
            end
        }
    }
--- request
    GET /re
--- response_body
12345
12345
--- no_error_log
[error]
attempt to get length of local 'subj' (a number value)



=== TEST 15: subject is not a string type
--- config
    location /re {
        content_by_lua_block {
            local m = ngx.re.match(12345, "123", "jo")

            if m then
                ngx.say(m[0])
            else
                ngx.say("not matched")
            end
        }
    }
--- request
    GET /re
--- response_body
123
--- no_error_log
[error]
attempt to get length of local 'regex' (a number value)
