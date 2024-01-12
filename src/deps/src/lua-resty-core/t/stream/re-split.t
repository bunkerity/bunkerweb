# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * blocks() * 4 + (2 * repeat_each());

no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: split matches, no submatch, no jit compile, no regex cache
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d", ",")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 2: split matches, no submatch, no jit compile, no regex cache
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a;,b;,c;,d;e", ";,")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d;e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 3: split matches, no submatch, jit compile, regex cache
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d", ",", "jo")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 4: split matches + submatch (matching)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a;,b;,c;,d,e", "(;),")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
;
b
;
c
;
d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 5: split matches + submatch (not matching)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", "(;)|,")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 6: split matches + max limiter
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, 3)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c,d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 7: split matches + submatch + max limiter
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", "(,)", nil, nil, 3)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
,
b
,
c,d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 8: split matches + max limiter set to 0
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, 0)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 9: split matches + max limiter set to a negative value
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, -1)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 10: split matches + max limiter set to 1
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, 1)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a,b,c,d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 11: split matches, provided res table
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local my_table = {}

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, nil, my_table)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 12: split matches, provided res table (non-cleared)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local my_table = {}

        for i = 1, 10 do
            my_table[i] = i.." hello world"
        end

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, nil, my_table)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i in ipairs(my_table) do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c
d
e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 13: split matches, provided res table + max limiter
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local my_table = {"hello, world"}

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, 3, my_table)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #my_table do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c,d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 14: split matches, provided res table (non-cleared) + max limiter
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local my_table = {}

        for i = 1, 10 do
            my_table[i] = i.." hello world"
        end

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, nil, 3, my_table)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i in ipairs(my_table) do
            ngx.say(res[i])
        end
    }
--- stream_response
a
b
c,d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 15: split matches, provided res table + max limiter + sub-match capturing group
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local my_table = {"hello, world"}

        local res, err = ngx_re.split("a,b,c,d,e", "(,)", nil, nil, 3, my_table)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #my_table do
            ngx.say(res[i])
        end
    }
--- stream_response
a
,
b
,
c,d,e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 16: split matches, ctx arg
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, { pos = 5 })
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
c
d
e
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 17: split matches, trailing subjects
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split(",a,b,c,d,", ",")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            if res[i] == "" then
                ngx.say("_blank_")
            else
                ngx.say(res[i])
            end
        end
    }
--- stream_response
_blank_
a
b
c
d
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
attempt to get length of local 'regex' (a number value)



=== TEST 18: split matches, real use-case
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("abcd,erfg,ghij;hello world;aaa", ",|;")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
abcd
erfg
ghij
hello world
aaa
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 19: split no matches
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("abcd", ",")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
abcd
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 20: subject is not a string type
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split(1234512345, "23", "jo")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
    }
--- stream_response
1
451
45
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
attempt to get length of local 'subj' (a number value)



=== TEST 21: split matches, pos is larger than subject length
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("a,b,c,d,e", ",", nil, { pos = 10 })
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end
        ngx.say("len: ", #res)
    }
--- stream_response
len: 0
--- no_error_log
[error]
[TRACE



=== TEST 22: regex is ""
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("12345", "", "jo")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end

        ngx.say("len: ", #res)
    }
--- stream_response
1
2
3
4
5
len: 5
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 23: regex is "" with max
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("12345", "", "jo", nil, 3)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end

        ngx.say("len: ", #res)
    }
--- stream_response
1
2
345
len: 3
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 24: regex is "" with pos
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("12345", "", "jo", { pos = 2 })
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end

        ngx.say("len: ", #res)
    }
--- stream_response
2
3
4
5
len: 4
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 25: regex is "" with pos larger than subject length
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("12345", "", "jo", { pos = 10 })
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end

        ngx.say("len: ", #res)
    }
--- stream_response
len: 0
--- no_error_log
[error]
[TRACE



=== TEST 26: regex is "" with pos & max
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("12345", "", "jo", { pos = 2 }, 2)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        for i = 1, #res do
            ngx.say(res[i])
        end

        ngx.say("len: ", #res)
    }
--- stream_response
2
345
len: 2
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 27: no match separator (github issue #104)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("abcd", "|")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))
        ngx.say("len: ", #res)
    }
--- stream_response
a:b:c:d
len: 4
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 28: no match separator (github issue #104) & max
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("abcd", "|", nil, nil, 2)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))
        ngx.say("len: ", #res)
    }
--- stream_response
a:bcd
len: 2
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 29: no match separator bis (github issue #104)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("abcd", "()")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))
        ngx.say("len: ", #res)
    }
--- stream_response
a::b::c::d
len: 7
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 30: behavior with /^/ differs from Perl's split
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("ab\ncd\nef", "^")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))

        ngx.say("len: ", #res)
    }
--- stream_response
ab
cd
ef
len: 1
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 31: behavior with /^/m
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("ab\ncd\nef", "^", "m")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))

        ngx.say("len: ", #res)
    }
--- stream_response
ab
:cd
:ef
len: 3
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 32: behavior with /^()/m (capture)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("ab\ncd\nef", "^()", "m")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))

        ngx.say("len: ", #res)
    }
--- stream_response
ab
::cd
::ef
len: 5
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 33: behavior with /^/m & max
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("ab\ncd\nef", "^", "m", nil, 2)
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))

        ngx.say("len: ", #res)
    }
--- stream_response
ab
:cd
ef
len: 2
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 34: behavior with /^\d/m
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("ab\n1cdefg\n2hij", "^\\d", "m")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))

        ngx.say("len: ", #res)
    }
--- stream_response
ab
:cdefg
:hij
len: 3
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 35: behavior with /^(\d)/m (capture)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local res, err = ngx_re.split("ab\n1cdefg\n2hij", "^(\\d)", "m")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(table.concat(res, ":"))

        ngx.say("len: ", #res)
    }
--- stream_response
ab
:1:cdefg
:2:hij
len: 5
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 36: split by unit separator 1/2 (GH issue lua-nginx-module #1217)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local subjs = {
            "1\x1fT\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f15",
            "1\x1fT\x1fT\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f15",
            "1\x1fT\x1fT\x1fT\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f15",
        }

        for _, subj in ipairs(subjs) do
            local col_list = ngx_re.split(subj, "\\x1f")
            ngx.say(#col_list, " ", table.concat(col_list, "|"))
        end
    }
--- stream_response
15 1|T|||||||||||||15
15 1|T|T||||||||||||15
15 1|T|T|T|||||||||||15
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 37: split by unit separator 2/2 (with ctx.pos)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local subjs = {
            "1\x1fT\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f15",
            "1\x1fT\x1fT\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f15",
            "1\x1fT\x1fT\x1fT\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f\x1f15",
        }

        for _, subj in ipairs(subjs) do
            local col_list = ngx_re.split(subj, "\\x1f", nil, { pos = 6 })
            ngx.say(#col_list, " ", table.concat(col_list, "|"))
        end
    }
--- stream_response
12 |||||||||||15
13 ||||||||||||15
13 |T|||||||||||15
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 38: remaining characters are matched by regex (without max)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local subj = "a,b,cd,,,"

        local res, err = ngx_re.split(subj, ",")
        if err then
            ngx.log(ngx.ERR, "failed: ", err)
            return
        end

        ngx.say(#res, " ", table.concat(res, "|"))
    }
--- stream_response
3 a|b|cd
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]



=== TEST 39: remaining characters are matched by regex (with max)
--- stream_server_config
    content_by_lua_block {
        local ngx_re = require "ngx.re"

        local subj = "a,b,cd,,,"

        for max = 1, 7 do
            local res, err = ngx_re.split(subj, ",", nil, nil, max)
            if err then
                ngx.log(ngx.ERR, "failed: ", err)
                return
            end

            ngx.say(#res, " ", table.concat(res, "|"))
        end
    }
--- stream_response
1 a,b,cd,,,
2 a|b,cd,,,
3 a|b|cd,,,
4 a|b|cd|,,
5 a|b|cd||,
6 a|b|cd|||
6 a|b|cd|||
--- error_log eval
qr/\[TRACE\s+\d+/
--- no_error_log
[error]
