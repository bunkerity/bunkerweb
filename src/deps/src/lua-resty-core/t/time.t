# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 6);

#no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.now()
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.now()
            end
            ngx.sleep(0.10)
            local elapsed = ngx.now() - t
            ngx.say(t > 1399867351)
            ngx.say(">= 0.099: ", elapsed >= 0.099)
            ngx.say("< 0.11: ", elapsed < 0.11)
            -- ngx.say(t, " ", elapsed)
        }
    }
--- request
GET /t
--- response_body
true
>= 0.099: true
< 0.11: true

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 2: ngx.time()
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.time()
            end
            ngx.say(t > 1400960598)
            local diff = os.time() - t
            ngx.say("<= 1: ", diff <= 1)
        }
    }
--- request
GET /t
--- response_body
true
<= 1: true

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 3: ngx.update_time()
--- config
    location = /t {
        content_by_lua_block {
            local start = ngx.now()
            for _ = 1, 1e5 do
                ngx.update_time()
            end
            ngx.say(ngx.now() - start > 0)
        }
    }
--- request
GET /t
--- response_body
true
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 4: ngx.today()
--- config
    location = /t {
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.today()
            end
            ngx.say(t)
        }
    }
--- request
GET /t
--- response_body_like: ^\d{4}-\d{2}-\d{2}
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 5: ngx.localtime()
--- config
    location = /t {
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.localtime()
            end
            ngx.say(t)
        }
    }
--- request
GET /t
--- response_body_like: ^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 6: ngx.utctime()
--- config
    location = /t {
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.utctime()
            end
            ngx.say(t)
        }
    }
--- request
GET /t
--- response_body_like: ^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 7: ngx.cookie_time()
--- config
    location /t {
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.cookie_time(1290079655)
            end
            ngx.say(t)
            ngx.say(ngx.cookie_time(2200000000))
        }
    }
--- request
GET /t
--- response_body
Thu, 18-Nov-10 11:27:35 GMT
Sun, 18-Sep-2039 23:06:40 GMT
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 8: ngx.cookie_time() bad argument
--- config
    location /t {
        content_by_lua_block {
            local pok, err = pcall(ngx.cookie_time, "foo")
            if not pok then
                ngx.say("not ok: ", err)
                return
            end

            ngx.say("ok")
        }
    }
--- request
GET /t
--- response_body
not ok: number argument only
--- no_error_log
[error]
[alert]
bad argument type
stitch



=== TEST 9: ngx.http_time()
--- config
    location /t {
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.http_time(1290079655)
            end
            ngx.say(t)
        }
    }
--- request
GET /t
--- response_body
Thu, 18 Nov 2010 11:27:35 GMT
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 10: ngx.http_time() bad argument
--- config
    location /t {
        content_by_lua_block {
            t = ngx.http_time(1290079655)
            local pok, err = pcall(ngx.http_time, "foo")
            if not pok then
                ngx.say("not ok: ", err)
                return
            end

            ngx.say("ok")

        }
    }
--- request
GET /t
--- response_body
not ok: number argument only
--- no_error_log
[error]
[alert]
bad argument type
stitch



=== TEST 11: ngx.parse_http_time()
--- config
    location /t {
        content_by_lua_block {
            local t
            for i = 1, 30 do
                t = ngx.parse_http_time("Thu, 18 Nov 2010 11:27:35 GMT")
            end
            ngx.say(t)
            ngx.say(ngx.parse_http_time("Thu, Nov 2010"))
        }
    }
--- request
GET /t
--- response_body
1290079655
nil
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):3 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 12: ngx.parse_http_time() bad argument
--- config
    location /t {
        content_by_lua_block {
            t = ngx.http_time(1290079655)
            local pok, err = pcall(ngx.parse_http_time, 123)
            if not pok then
                ngx.say("not ok: ", err)
                return
            end

            ngx.say("ok")

        }
    }
--- request
GET /t
--- response_body
not ok: string argument only
--- no_error_log
[error]
[alert]
bad argument type
stitch



=== TEST 13: "resty.core.time".monotonic_msec
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local cur_msec = require "resty.core.time".monotonic_msec
            local proc = io.open("/proc/uptime", "r")
            local content = proc:read()
            proc:close()
            local idx = string.find(content, " ", 1, true)
            local uptime = 1000 * tonumber(string.sub(content, 1, idx - 1))
            ngx.update_time()

            local t
            for i = 1, 30 do
                t = cur_msec()
            end
            ngx.say(t >= uptime)
            local diff = t - uptime
            ngx.say("< 10: ", diff < 10)
        }
    }
--- request
GET /t
--- response_body
true
< 10: true

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):11 loop\]/
--- no_error_log
[error]
bad argument type
stitch



=== TEST 14: "resty.core.time".monotonic_time
--- config
    location = /t {
        access_log off;
        content_by_lua_block {
            local cur_time = require "resty.core.time".monotonic_time
            local proc = io.open("/proc/uptime", "r")
            local content = proc:read()
            proc:close()
            local idx = string.find(content, " ", 1, true)
            local uptime = tonumber(string.sub(content, 1, idx - 1))
            ngx.update_time()

            local t
            for i = 1, 30 do
                t = cur_time()
            end
            ngx.say(t >= uptime)
            local diff = t - uptime
            ngx.say("< 0.01: ", diff < 0.01)
        }
    }
--- request
GET /t
--- response_body
true
< 0.01: true

--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):11 loop\]/
--- no_error_log
[error]
bad argument type
stitch
