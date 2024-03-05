# vim:set ts=4 sts=4 sw=4 et ft=:

use strict;
use lib '.';
use t::TestMLCache;

workers(2);
#repeat_each(2);

plan tests => repeat_each() * blocks() * 4;

run_tests();

__DATA__

=== TEST 1: update() with ipc_shm catches up with invalidation events
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }))

            cache.ipc:subscribe(cache.events.invalidation.channel, function(data)
                ngx.log(ngx.NOTICE, "received event from invalidations: ", data)
            end)

            assert(cache:delete("my_key"))
            assert(cache:update())
        }
    }
--- ignore_response_body
--- error_log
received event from invalidations: my_key
--- no_error_log
[error]
[crit]



=== TEST 2: update() with ipc_shm timeouts when waiting for too long
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }))

            cache.ipc:subscribe(cache.events.invalidation.channel, function(data)
                ngx.log(ngx.NOTICE, "received event from invalidations: ", data)
            end)

            assert(cache:delete("my_key"))
            assert(cache:delete("my_other_key"))
            ngx.shared.ipc_shm:delete(2)

            local ok, err = cache:update(0.1)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
could not poll ipc events: timeout
--- error_log
received event from invalidations: my_key
--- no_error_log
[error]
received event from invalidations: my_other



=== TEST 3: update() with ipc_shm JITs when no events to catch up
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"
            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }))
            for i = 1, 10e3 do
                assert(cache:update())
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):7 loop\]/
--- no_error_log
[error]
[crit]



=== TEST 4: set() with ipc_shm invalidates other workers' LRU cache
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local opts = {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }

            local cache = assert(mlcache.new("namespace", "cache_shm", opts))
            local cache_clone = assert(mlcache.new("namespace", "cache_shm", opts))

            do
                local lru_delete = cache.lru.delete
                cache.lru.delete = function(self, key)
                    ngx.say("called lru:delete() with key: ", key)
                    return lru_delete(self, key)
                end
            end

            assert(cache:set("my_key", nil, nil))

            ngx.say("calling update on cache")
            assert(cache:update())

            ngx.say("calling update on cache_clone")
            assert(cache_clone:update())
        }
    }
--- response_body
calling update on cache
called lru:delete() with key: my_key
calling update on cache_clone
called lru:delete() with key: my_key
--- no_error_log
[error]
[crit]



=== TEST 5: delete() with ipc_shm invalidates other workers' LRU cache
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local opts = {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }

            local cache = assert(mlcache.new("namespace", "cache_shm", opts))
            local cache_clone = assert(mlcache.new("namespace", "cache_shm", opts))

            do
                local lru_delete = cache.lru.delete
                cache.lru.delete = function(self, key)
                    ngx.say("called lru:delete() with key: ", key)
                    return lru_delete(self, key)
                end
            end

            assert(cache:delete("my_key"))

            ngx.say("calling update on cache")
            assert(cache:update())

            ngx.say("calling update on cache_clone")
            assert(cache_clone:update())
        }
    }
--- response_body
called lru:delete() with key: my_key
calling update on cache
called lru:delete() with key: my_key
calling update on cache_clone
called lru:delete() with key: my_key
--- no_error_log
[error]
[crit]



=== TEST 6: purge() with mlcache_shm invalidates other workers' LRU cache (OpenResty < 1.13.6.2)
--- skip_eval: 3: t::TestMLCache::skip_openresty('>=', '1.13.6.2')
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local opts = {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }

            local cache = assert(mlcache.new("namespace", "cache_shm", opts))
            local cache_clone = assert(mlcache.new("namespace", "cache_shm", opts))

            local lru = cache.lru
            local lru_clone = cache_clone.lru

            assert(cache:purge())

            -- cache.lru should be different now
            ngx.say("cache has new lru: ", cache.lru ~= lru)

            ngx.say("cache_clone still has same lru: ", cache_clone.lru == lru_clone)

            ngx.say("calling update on cache_clone")
            assert(cache_clone:update())

            -- cache.lru should be different now
            ngx.say("cache_clone has new lru: ", cache_clone.lru ~= lru_clone)
        }
    }
--- response_body
cache has new lru: true
cache_clone still has same lru: true
calling update on cache_clone
cache_clone has new lru: true
--- no_error_log
[error]
[crit]



=== TEST 7: purge() with mlcache_shm invalidates other workers' LRU cache (OpenResty >= 1.13.6.2)
--- skip_eval: 3: t::TestMLCache::skip_openresty('<', '1.13.6.2')
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local opts = {
                ipc_shm = "ipc_shm",
                debug = true -- allows same worker to receive its own published events
            }

            local cache = assert(mlcache.new("namespace", "cache_shm", opts))
            local cache_clone = assert(mlcache.new("namespace", "cache_shm", opts))

            local lru = cache.lru

            ngx.say("both instances use the same lru: ", cache.lru == cache_clone.lru)

            do
                local lru_flush_all = lru.flush_all
                cache.lru.flush_all = function(self)
                    ngx.say("called lru:flush_all()")
                    return lru_flush_all(self)
                end
            end

            assert(cache:purge())

            ngx.say("calling update on cache_clone")
            assert(cache_clone:update())

            ngx.say("both instances use the same lru: ", cache.lru == cache_clone.lru)
            ngx.say("lru didn't change after purge: ", cache.lru == lru)
        }
    }
--- response_body
both instances use the same lru: true
called lru:flush_all()
calling update on cache_clone
called lru:flush_all()
both instances use the same lru: true
lru didn't change after purge: true
--- no_error_log
[error]
[crit]
