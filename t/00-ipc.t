# vim:set ts=4 sts=4 sw=4 et ft=:

use strict;
use lib '.';
use t::TestMLCache;

plan tests => repeat_each() * blocks() * 5;

run_tests();

__DATA__

=== TEST 1: new() ensures shm exists
--- config
    location /t {
        content_by_lua_block {
            local mlcache_ipc = require "resty.mlcache.ipc"

            local ipc, err = mlcache_ipc.new("foo")
            ngx.say(err)
        }
    }
--- response_body
no such lua_shared_dict: foo
--- no_error_log
[error]
[crit]
[alert]



=== TEST 2: broadcast() sends an event through shm
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "received event from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "hello world"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- error_log
received event from my_channel: hello world
--- no_error_log
[error]
[crit]
[alert]



=== TEST 3: broadcast() runs event callback in protected mode
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            error("my callback had an error")
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "hello world"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[error\] .*? \[ipc\] callback for channel 'my_channel' threw a Lua error: init_worker_by_lua(.*?)?:\d: my callback had an error/
--- no_error_log
lua entry thread aborted: runtime error
[crit]
[alert]



=== TEST 4: poll() catches invalid timeout arg
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))
    }
--- config
    location /t {
        content_by_lua_block {
            local ok, err = pcall(ipc.poll, ipc, false)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
timeout must be a number
--- no_error_log
[error]
[crit]
[alert]



=== TEST 5: poll() catches up with all events
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "received event from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "msg 1"))
            assert(ipc:broadcast("my_channel", "msg 2"))
            assert(ipc:broadcast("my_channel", "msg 3"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- error_log
received event from my_channel: msg 1
received event from my_channel: msg 2
received event from my_channel: msg 3
--- no_error_log
[error]



=== TEST 6: poll() resumes to current idx if events were previously evicted
This ensures new workers spawned during a master process' lifecycle do not
attempt to replay all events from index 0.
https://github.com/thibaultcha/lua-resty-mlcache/issues/87
https://github.com/thibaultcha/lua-resty-mlcache/issues/93
--- http_config
    lua_shared_dict  ipc_shm 32k;

    init_by_lua_block {
        require "resty.core"
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "my_channel event: ", data)
        end)

        for i = 1, 32 do
            -- fill shm, simulating busy workers
            -- this must trigger eviction for this test to succeed
            assert(ipc:broadcast("my_channel", string.rep(".", 2^10)))
        end
    }
--- config
    location /t {
        content_by_lua_block {
            ngx.say("ipc.idx: ", ipc.idx)

            assert(ipc:broadcast("my_channel", "first broadcast"))
            assert(ipc:broadcast("my_channel", "second broadcast"))

            -- first poll without new() to simulate new worker
            assert(ipc:poll())

            -- ipc.idx set to shm_idx-1 ("second broadcast")
            ngx.say("ipc.idx: ", ipc.idx)
        }
    }
--- response_body
ipc.idx: 0
ipc.idx: 34
--- error_log
my_channel event: second broadcast
--- no_error_log
my_channel event: first broadcast
[error]



=== TEST 7: poll() does not execute events from self (same pid)
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm"))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "received event from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "hello world"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- no_error_log
received event from my_channel: hello world
[error]
[crit]
[alert]



=== TEST 8: poll() runs all registered callbacks for a channel
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 1 from my_channel: ", data)
        end)

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 2 from my_channel: ", data)
        end)

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 3 from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "hello world"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- error_log
callback 1 from my_channel: hello world
callback 2 from my_channel: hello world
callback 3 from my_channel: hello world
--- no_error_log
[error]



=== TEST 9: poll() exits when no event to poll
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- no_error_log
callback from my_channel: hello world
[error]
[crit]
[alert]



=== TEST 10: poll() runs all callbacks from all channels
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 1 from my_channel: ", data)
        end)

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 2 from my_channel: ", data)
        end)

        ipc:subscribe("other_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 1 from other_channel: ", data)
        end)

        ipc:subscribe("other_channel", function(data)
            ngx.log(ngx.NOTICE, "callback 2 from other_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "hello world"))
            assert(ipc:broadcast("other_channel", "hello ipc"))
            assert(ipc:broadcast("other_channel", "hello ipc 2"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- grep_error_log eval: qr/callback \d+ from [^,]*/
--- grep_error_log_out
callback 1 from my_channel: hello world
callback 2 from my_channel: hello world
callback 1 from other_channel: hello ipc
callback 2 from other_channel: hello ipc
callback 1 from other_channel: hello ipc 2
callback 2 from other_channel: hello ipc 2
--- no_error_log
[error]
[crit]
[alert]



=== TEST 11: poll() catches tampered shm (by third-party users)
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "msg 1"))

            assert(ngx.shared.ipc_shm:set("lua-resty-ipc:index", false))

            local ok, err = ipc:poll()
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
index is not a number, shm tampered with
--- no_error_log
[error]
[crit]
[alert]



=== TEST 12: poll() retries getting an event until timeout
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "msg 1"))

            ngx.shared.ipc_shm:delete(1)
            ngx.shared.ipc_shm:flush_expired()

            local ok, err = ipc:poll()
            if not ok then
                ngx.log(ngx.ERR, "could not poll: ", err)
            end
        }
    }
--- ignore_response_body
--- grep_error_log eval: qr/((\[error\] .*?)|(\[ipc\] no event data at index '\d+', retrying .*?))[^,]*/
--- grep_error_log_out eval
qr/\[ipc\] no event data at index '1', retrying in: 0\.001s
\[ipc\] no event data at index '1', retrying in: 0\.002s
\[ipc\] no event data at index '1', retrying in: 0\.004s
\[ipc\] no event data at index '1', retrying in: 0\.008s
\[ipc\] no event data at index '1', retrying in: 0\.016s
\[ipc\] no event data at index '1', retrying in: 0\.032s
\[ipc\] no event data at index '1', retrying in: 0\.064s
\[ipc\] no event data at index '1', retrying in: 0\.128s
\[ipc\] no event data at index '1', retrying in: 0\.045s
\[error\] .*? could not poll: timeout/
--- no_error_log
[warn]
[crit]
[alert]



=== TEST 13: poll() reaches custom timeout
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "msg 1"))

            ngx.shared.ipc_shm:delete(1)
            ngx.shared.ipc_shm:flush_expired()

            local ok, err = ipc:poll(0.01)
            if not ok then
                ngx.log(ngx.ERR, "could not poll: ", err)
            end
        }
    }
--- ignore_response_body
--- grep_error_log eval: qr/((\[error\] .*?)|(\[ipc\] no event data at index '\d+', retrying .*?))[^,]*/
--- grep_error_log_out eval
qr/\[ipc\] no event data at index '1', retrying in: 0\.001s
\[ipc\] no event data at index '1', retrying in: 0\.002s
\[ipc\] no event data at index '1', retrying in: 0\.004s
\[ipc\] no event data at index '1', retrying in: 0\.003s
\[error\] .*? could not poll: timeout/
--- no_error_log
[warn]
[crit]
[alert]



=== TEST 14: poll() logs errors and continue if event has been tampered with
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("my_channel", "msg 1"))
            assert(ipc:broadcast("my_channel", "msg 2"))

            assert(ngx.shared.ipc_shm:set(1, false))

            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- error_log eval
[
    qr/\[error\] .*? \[ipc\] event at index '1' is not a string, shm tampered with/,
    qr/\[notice\] .*? callback from my_channel: msg 2/,
]
--- no_error_log
[warn]
[crit]



=== TEST 15: poll() is safe to be called in contexts that don't support ngx.sleep()
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback from my_channel: ", data)
        end)
    }
--- config
    location /t {
        return 200;

        log_by_lua_block {
            assert(ipc:broadcast("my_channel", "msg 1"))

            ngx.shared.ipc_shm:delete(1)
            ngx.shared.ipc_shm:flush_expired()

            local ok, err = ipc:poll()
            if not ok then
                ngx.log(ngx.ERR, "could not poll: ", err)
            end
        }
    }
--- ignore_response_body
--- error_log eval
[
    qr/\[info\] .*? \[ipc\] no event data at index '1', retrying in: 0\.001s/,
    qr/\[warn\] .*? \[ipc\] could not sleep before retry: API disabled in the context of log_by_lua/,
    qr/\[error\] .*? could not poll: timeout/,
]
--- no_error_log
[crit]



=== TEST 16: poll() guards self.idx from growing beyond the current shm idx
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            assert(ipc:broadcast("other_channel", ""))
            assert(ipc:poll())
            assert(ipc:broadcast("my_channel", "fist broadcast"))
            assert(ipc:broadcast("other_channel", ""))
            assert(ipc:broadcast("my_channel", "second broadcast"))

            -- shm idx is 5, let's mess with the instance's idx
            ipc.idx = 10
            assert(ipc:poll())

            -- we may have skipped the above events, but we are able to resume polling
            assert(ipc:broadcast("other_channel", ""))
            assert(ipc:broadcast("my_channel", "third broadcast"))
            assert(ipc:poll())
        }
    }
--- ignore_response_body
--- error_log
callback from my_channel: third broadcast
--- no_error_log
callback from my_channel: first broadcast
callback from my_channel: second broadcast
[error]



=== TEST 17: poll() JITs
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            for i = 1, 10e3 do
                assert(ipc:poll())
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):2 loop\]/
--- no_error_log
[warn]
[error]
[crit]



=== TEST 18: broadcast() JITs
--- http_config
    init_worker_by_lua_block {
        local mlcache_ipc = require "resty.mlcache.ipc"

        ipc = assert(mlcache_ipc.new("ipc_shm", true))

        ipc:subscribe("my_channel", function(data)
            ngx.log(ngx.NOTICE, "callback from my_channel: ", data)
        end)
    }
--- config
    location /t {
        content_by_lua_block {
            for i = 1, 10e3 do
                assert(ipc:broadcast("my_channel", "hello world"))
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):2 loop\]/
--- no_error_log
[warn]
[error]
[crit]
