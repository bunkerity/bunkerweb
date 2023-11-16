# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
log_level('debug');

repeat_each(2);

plan tests => repeat_each() * 39;

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: sleep 0.5 - content
--- stream_server_config
    content_by_lua_block {
        ngx.update_time()
        local before = ngx.now()
        ngx.sleep(0.5)
        local now = ngx.now()
        ngx.say(now - before)
    }
--- stream_response_like chop
^0\.(?:4[5-9]\d*|5[0-5]\d*|5)$
--- error_log
lua ready to sleep for
stream lua sleep timer expired



=== TEST 2: sleep a - content
--- stream_server_config
    content_by_lua_block {
        ngx.update_time()
        local before = ngx.now()
        ngx.sleep("a")
        local now = ngx.now()
        ngx.say(now - before)
    }
--- stream_response
--- error_log
bad argument #1 to 'sleep'



=== TEST 3: sleep 0.33 - multi-times in content
--- stream_server_config
    content_by_lua_block {
        ngx.update_time()
        local start = ngx.now()
        ngx.sleep(0.33)
        ngx.sleep(0.33)
        ngx.sleep(0.33)
        ngx.say(ngx.now() - start)
    }
--- stream_response_like chop
^(?:0\.9\d*|1\.[0-2]\d*|1)$
--- error_log
lua ready to sleep for
stream lua sleep timer expired
--- no_error_log
[error]



=== TEST 4: sleep 0.5 - interleaved by ngx.say() - ended by ngx.sleep
--- stream_server_config
    content_by_lua_block {
        ngx.sleep(1)
        ngx.say("blah")
        ngx.sleep(1)
    }
--- stream_response
blah
--- error_log
lua ready to sleep
stream lua sleep timer expired
--- no_error_log
[error]



=== TEST 5: sleep 0.5 - interleaved by ngx.say() - not ended by ngx.sleep
--- stream_server_config
    content_by_lua_block {
        ngx.sleep(0.3)
        ngx.say("blah")
        ngx.sleep(0.5)
        ngx.say("hiya")
    }
--- stream_response
blah
hiya
--- error_log
lua ready to sleep for
stream lua sleep timer expired
--- no_error_log
[error]



=== TEST 6: sleep 0
--- stream_server_config
    content_by_lua_block {
        ngx.update_time()
        local before = ngx.now()
        ngx.sleep(0)
        local now = ngx.now()
        ngx.say("elapsed: ", now - before)
    }
--- stream_response_like chop
elapsed: 0
--- error_log
lua ready to sleep for
stream lua sleep timer expired
--- no_error_log
[error]



=== TEST 7: ngx.sleep unavailable in log_by_lua
TODO
--- SKIP
--- stream_server_config
        echo hello;
    log_by_lua_block {
        ngx.sleep(0.1)
    }
--- stream_response
hello
--- wait: 0.1
--- error_log
API disabled in the context of log_by_lua*



=== TEST 8: ngx.sleep() fails to yield (xpcall err handler)
--- stream_server_config
    content_by_lua_block {
        local function f()
            return error(1)
        end
        local function err()
            ngx.sleep(0.001)
        end
        xpcall(f, err)
        ngx.say("ok")
    }
--- stream_response
ok
--- error_log
lua clean up the timer for pending ngx.sleep
--- no_error_log
[error]



=== TEST 9: ngx.sleep() fails to yield (require)
--- stream_config
    lua_package_path "$prefix/html/?.lua;;";
--- stream_server_config
    content_by_lua_block {
        package.loaded["foosleep"] = nil
        require "foosleep";
    }
--- user_files
>>> foosleep.lua
ngx.sleep(0.001)

--- stream_response
--- wait: 0.2
--- error_log eval
[
"lua clean up the timer for pending ngx.sleep",
qr{runtime error: attempt to yield across (?:metamethod/)?C-call boundary},
]



=== TEST 10: sleep coctx handler did not get called in ngx.exit().
--- stream_server_config
    content_by_lua_block {
        local function sleep(t)
            --- nginx return reply to client without waiting
            ngx.sleep(t)
        end

        local function wait()
             --- worker would crash afterwards
             xpcall(function () error(1) end, function() return sleep(0.001) end)
             --- ngx.exit was required to crash worker
             ngx.exit(200)
        end

        wait()
    }
--- wait: 0.1
--- stream_response
--- no_error_log
[error]
[alert]
