# vi:ft=

use lib '.';
use t::TestKiller;

plan tests => 3 * blocks();

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: returns an error if signal is unknown
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local ok, err = resty_signal.kill(pid, "FOO")
            if not ok then
                ngx.say("failed to send FOO signal: ", err)
                return
            end
            ngx.say("ok")
        }
    }
--- response_body
failed to send FOO signal: unknown signal name



=== TEST 2: send NONE to a non-existing process
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local say = ngx.say
            local ngx_pipe = require "ngx.pipe"
            local proc = assert(ngx_pipe.spawn("echo ok"))
            local pid = assert(proc:pid())
            assert(proc:wait())

            local ok, err = resty_signal.kill(pid, "NONE")
            if not ok then
                ngx.say("failed to send NONE signal: ", err)
                return
            end
            ngx.say("ok")
        }
    }
--- response_body
failed to send NONE signal: No such process



=== TEST 3: send TERM to a non-existing process
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local say = ngx.say
            local ngx_pipe = require "ngx.pipe"
            local proc = assert(ngx_pipe.spawn("echo ok"))
            local pid = assert(proc:pid())
            assert(proc:wait())

            local ok, err = resty_signal.kill(pid, "TERM")
            if not ok then
                ngx.say("failed to send TERM signal: ", err)
                return
            end
            ngx.say("ok")
        }
    }
--- response_body
failed to send TERM signal: No such process



=== TEST 4: send NONE to an existing process
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local say = ngx.say
            local ngx_pipe = require "ngx.pipe"
            local proc = assert(ngx_pipe.spawn("echo ok"))
            local pid = assert(proc:pid())
            -- assert(proc:wait())

            for i = 1, 2 do
                ngx.say("i = ", i)
                local ok, err = resty_signal.kill(pid, "NONE")
                if not ok then
                    ngx.say("failed to send NONE signal: ", err)
                    return
                end
            end

            ngx.say("ok")
        }
    }
--- response_body
i = 1
i = 2
ok



=== TEST 5: send TERM to an existing process
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local say = ngx.say
            local ngx_pipe = require "ngx.pipe"
            local proc = assert(ngx_pipe.spawn("echo ok"))
            local pid = assert(proc:pid())
            -- assert(proc:wait())

            for i = 1, 2 do
                ngx.say("i = ", i)
                local ok, err = resty_signal.kill(pid, "TERM")
                if not ok then
                    ngx.say("failed to send TERM signal: ", err)
                    return
                end
                ngx.sleep(0.01)
            end

            ngx.say("ok")
        }
    }
--- response_body
i = 1
i = 2
failed to send TERM signal: No such process



=== TEST 6: send KILL to an existing process
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local say = ngx.say
            local ngx_pipe = require "ngx.pipe"
            local proc = assert(ngx_pipe.spawn("echo ok"))
            local pid = assert(proc:pid())
            -- assert(proc:wait())

            for i = 1, 2 do
                ngx.say("i = ", i)
                local ok, err = resty_signal.kill(pid, "KILL")
                if not ok then
                    ngx.say("failed to send KILL signal: ", err)
                    return
                end
                ngx.sleep(0.01)
            end

            ngx.say("ok")
        }
    }
--- response_body
i = 1
i = 2
failed to send KILL signal: No such process



=== TEST 7: send TERM signal value, 15, directly to an existing process
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"

            local say = ngx.say
            local ngx_pipe = require "ngx.pipe"
            local proc = assert(ngx_pipe.spawn("echo ok"))
            local pid = assert(proc:pid())
            -- assert(proc:wait())

            for i = 1, 2 do
                ngx.say("i = ", i)
                local ok, err = resty_signal.kill(pid, 15)
                if not ok then
                    ngx.say("failed to send TERM signal: ", err)
                    return
                end
                ngx.sleep(0.01)
            end

            ngx.say("ok")
        }
    }
--- response_body
i = 1
i = 2
failed to send TERM signal: No such process
