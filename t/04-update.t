# vim:set ts=4 sts=4 sw=4 et ft=:

use strict;
use lib '.';
use t::TestMLCache;

workers(2);
#repeat_each(2);

plan tests => repeat_each() * blocks() * 3;

run_tests();

__DATA__

=== TEST 1: update() errors if no ipc
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm"))

            local ok, err = pcall(cache.update, cache, "foo")
            ngx.say(err)
        }
    }
--- response_body
no polling configured, specify opts.ipc_shm or opts.ipc.poll
--- no_error_log
[error]



=== TEST 2: update() calls ipc poll() with timeout arg
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ipc = {
                    register_listeners = function() end,
                    broadcast = function() end,
                    poll = function(...)
                        ngx.say("called poll() with args: ", ...)
                        return true
                    end,
                }
            }))

            assert(cache:update(3.5, "not me"))
        }
    }
--- response_body
called poll() with args: 3.5
--- no_error_log
[error]



=== TEST 3: update() JITs when no events to catch up
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
            }))

            for i = 1, 10e3 do
                assert(cache:update())
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):8 loop\]/
--- no_error_log
[error]
