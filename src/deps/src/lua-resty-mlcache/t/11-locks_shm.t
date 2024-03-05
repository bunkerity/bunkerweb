# vim:set ts=4 sts=4 sw=4 et ft=:

use strict;
use lib '.';
use t::TestMLCache;

plan tests => repeat_each() * blocks() * 3;

run_tests();

__DATA__

=== TEST 1: new() validates opts.shm_locks
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local ok, err = pcall(mlcache.new, "name", "cache_shm", {
                shm_locks = false,
            })
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
opts.shm_locks must be a string
--- no_error_log
[error]



=== TEST 2: new() ensures opts.shm_locks exists
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local ok, err = mlcache.new("name", "cache_shm", {
                shm_locks = "foo",
            })
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
no such lua_shared_dict for opts.shm_locks: foo
--- no_error_log
[error]



=== TEST 3: get() stores resty-locks in opts.shm_locks if specified
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("name", "cache_shm", {
                shm_locks = "locks_shm",
            }))

            local function cb()
                local keys = ngx.shared.locks_shm:get_keys()
                for i, key in ipairs(keys) do
                    ngx.say(i, ": ", key)
                end

                return 123
            end

            cache:get("key", nil, cb)
        }
    }
--- response_body
1: lua-resty-mlcache:lock:namekey
--- no_error_log
[error]
