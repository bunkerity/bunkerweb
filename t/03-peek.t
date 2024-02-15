# vim:set ts=4 sts=4 sw=4 et ft=:

use strict;
use lib '.';
use t::TestMLCache;

workers(2);
#repeat_each(2);

plan tests => repeat_each() * (blocks() * 4);

run_tests();

__DATA__

=== TEST 1: peek() validates key
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = pcall(cache.peek, cache)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
key must be a string
--- no_error_log
[error]
[crit]



=== TEST 2: peek() returns nil if a key has never been fetched before
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ttl, err = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", ttl)
        }
    }
--- response_body
ttl: nil
--- no_error_log
[error]
[crit]



=== TEST 3: peek() returns the remaining ttl if a key has been fetched before
--- main_config
    timer_resolution 10ms;
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local function cb()
                return nil
            end

            local val, err = cache:get("my_key", { neg_ttl = 19 }, cb)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            local ttl, err = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl))

            ngx.sleep(1)

            local ttl, err = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl))
        }
    }
--- response_body
ttl: 19
ttl: 18
--- no_error_log
[error]
[crit]



=== TEST 4: peek() returns a 0 remaining_ttl if the ttl was 0
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm"))

            local function cb()
                return nil
            end

            local val, err = cache:get("my_key", { neg_ttl = 0 }, cb)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.sleep(1)

            local ttl = assert(cache:peek("my_key"))
            ngx.say("ttl: ", math.ceil(ttl))

            ngx.sleep(1)

            local ttl = assert(cache:peek("my_key"))
            ngx.say("ttl: ", math.ceil(ttl))
        }
    }
--- response_body
ttl: 0
ttl: 0
--- no_error_log
[error]
[crit]



=== TEST 5: peek() returns remaining ttl if shm_miss is specified
--- main_config
    timer_resolution 10ms;
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                shm_miss = "cache_shm_miss",
            }))

            local function cb()
                return nil
            end

            local val, err = cache:get("my_key", { neg_ttl = 19 }, cb)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            local ttl, err = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl))

            ngx.sleep(1)

            local ttl, err = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl))
        }
    }
--- response_body
ttl: 19
ttl: 18
--- no_error_log
[error]
[crit]



=== TEST 6: peek() returns the value if a key has been fetched before
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local function cb_number()
                return 123
            end

            local function cb_nil()
                return nil
            end

            local val, err = cache:get("my_key", nil, cb_number)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            local val, err = cache:get("my_nil_key", nil, cb_nil)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            local ttl, err, val = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl), " val: ", val)

            local ttl, err, val = cache:peek("my_nil_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl), " nil_val: ", val)
        }
    }
--- response_body_like
ttl: \d* val: 123
ttl: \d* nil_val: nil
--- no_error_log
[error]
[crit]



=== TEST 7: peek() returns the value if shm_miss is specified
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                shm_miss = "cache_shm_miss",
            }))

            local function cb_nil()
                return nil
            end

            local val, err = cache:get("my_nil_key", nil, cb_nil)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            local ttl, err, val = cache:peek("my_nil_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", math.ceil(ttl), " nil_val: ", val)
        }
    }
--- response_body_like
ttl: \d* nil_val: nil
--- no_error_log
[error]
[crit]



=== TEST 8: peek() JITs on hit
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm"))

            local function cb()
                return 123456
            end

            local val = assert(cache:get("key", nil, cb))
            ngx.say("val: ", val)

            for i = 1, 10e3 do
                assert(cache:peek("key"))
            end
        }
    }
--- response_body
val: 123456
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):13 loop\]/
--- no_error_log
[error]



=== TEST 9: peek() JITs on miss
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm"))

            for i = 1, 10e3 do
                local ttl, err, val = cache:peek("key")
                assert(err == nil)
                assert(ttl == nil)
                assert(val == nil)
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):6 loop\]/
--- no_error_log
[error]
[crit]



=== TEST 10: peek() returns nil if a value expired
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            assert(cache:get("my_key", { ttl = 0.3 }, function()
                return 123
            end))

            ngx.sleep(0.3)

            local ttl, err, data, stale = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", ttl)
            ngx.say("data: ", data)
            ngx.say("stale: ", stale)
        }
    }
--- response_body
ttl: nil
data: nil
stale: nil
--- no_error_log
[error]
[crit]



=== TEST 11: peek() returns nil if a value expired in 'shm_miss'
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                shm_miss = "cache_shm_miss"
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("my_key", { neg_ttl = 0.3 }, function()
                return nil
            end)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.sleep(0.3)

            local ttl, err, data, stale = cache:peek("my_key")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", ttl)
            ngx.say("data: ", data)
            ngx.say("stale: ", stale)
        }
    }
--- response_body
ttl: nil
data: nil
stale: nil
--- no_error_log
[error]
[crit]



=== TEST 12: peek() accepts stale arg and returns stale values
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            assert(cache:get("my_key", { ttl = 0.3 }, function()
                return 123
            end))

            ngx.sleep(0.3)

            local ttl, err, data, stale = cache:peek("my_key", true)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", ttl)
            ngx.say("data: ", data)
            ngx.say("stale: ", stale)
        }
    }
--- response_body_like chomp
ttl: -0\.\d+
data: 123
stale: true
--- no_error_log
[error]
[crit]



=== TEST 13: peek() accepts stale arg and returns stale values from 'shm_miss'
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                shm_miss = "cache_shm_miss"
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("my_key", { neg_ttl = 0.3 }, function()
                return nil
            end)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.sleep(0.3)

            local ttl, err, data, stale = cache:peek("my_key", true)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say("ttl: ", ttl)
            ngx.say("data: ", data)
            ngx.say("stale: ", stale)
        }
    }
--- response_body_like chomp
ttl: -0\.\d+
data: nil
stale: true
--- no_error_log
[error]
[crit]



=== TEST 14: peek() does not evict stale items from L2 shm
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"
            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ttl = 0.3,
            }))

            local data, err = cache:get("key", nil, function()
                return 123
            end)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.sleep(0.3)

            for i = 1, 3 do
                remaining_ttl, err, data = cache:peek("key", true)
                if err then
                    ngx.log(ngx.ERR, err)
                    return
                end
                ngx.say("remaining_ttl: ", remaining_ttl)
                ngx.say("data: ", data)
            end
        }
    }
--- response_body_like chomp
remaining_ttl: -\d\.\d+
data: 123
remaining_ttl: -\d\.\d+
data: 123
remaining_ttl: -\d\.\d+
data: 123
--- no_error_log
[error]
[crit]



=== TEST 15: peek() does not evict stale negative data from L2 shm_miss
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"
            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                neg_ttl = 0.3,
                shm_miss = "cache_shm_miss",
            }))

            local data, err = cache:get("key", nil, function()
                return nil
            end)
            if err then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.sleep(0.3)

            for i = 1, 3 do
                remaining_ttl, err, data = cache:peek("key", true)
                if err then
                    ngx.log(ngx.ERR, err)
                    return
                end
                ngx.say("remaining_ttl: ", remaining_ttl)
                ngx.say("data: ", data)
            end
        }
    }
--- response_body_like chomp
remaining_ttl: -\d\.\d+
data: nil
remaining_ttl: -\d\.\d+
data: nil
remaining_ttl: -\d\.\d+
data: nil
--- no_error_log
[error]
[crit]
