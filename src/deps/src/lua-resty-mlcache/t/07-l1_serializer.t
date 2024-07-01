# vim:set ts=4 sts=4 sw=4 et ft=:

use strict;
use lib '.';
use t::TestMLCache;

workers(2);
#repeat_each(2);

plan tests => repeat_each() * blocks() * 3;

run_tests();

__DATA__

=== TEST 1: l1_serializer is validated by the constructor
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local ok, err = pcall(mlcache.new, "my_mlcache", "cache_shm", {
                l1_serializer = false,
            })
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
opts.l1_serializer must be a function
--- no_error_log
[error]



=== TEST 2: l1_serializer is called on L1+L2 cache misses
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    return string.format("transform(%q)", s)
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("key", nil, function() return "foo" end)
            if not data then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(data)
        }
    }
--- response_body
transform("foo")
--- no_error_log
[error]



=== TEST 3: get() JITs when hit of scalar value coming from shm with l1_serializer
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(i)
                    return i + 2
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local function cb_number()
                return 123456
            end

            for i = 1, 10e2 do
                local data = assert(cache:get("number", nil, cb_number))
                assert(data == 123458)

                cache.lru:delete("number")
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):18 loop\]/
--- no_error_log
[error]



=== TEST 4: l1_serializer is not called on L1 hits
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local calls = 0
            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    calls = calls + 1
                    return string.format("transform(%q)", s)
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            for i = 1, 3 do
                local data, err = cache:get("key", nil, function() return "foo" end)
                if not data then
                    ngx.log(ngx.ERR, err)
                    return
                end

                ngx.say(data)
            end

            ngx.say("calls: ", calls)
        }
    }
--- response_body
transform("foo")
transform("foo")
transform("foo")
calls: 1
--- no_error_log
[error]



=== TEST 5: l1_serializer is called on each L2 hit
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local calls = 0
            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    calls = calls + 1
                    return string.format("transform(%q)", s)
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            for i = 1, 3 do
                local data, err = cache:get("key", nil, function() return "foo" end)
                if not data then
                    ngx.log(ngx.ERR, err)
                    return
                end

                ngx.say(data)
                cache.lru:delete("key")
            end

            ngx.say("calls: ", calls)
        }
    }
--- response_body
transform("foo")
transform("foo")
transform("foo")
calls: 3
--- no_error_log
[error]



=== TEST 6: l1_serializer is called on boolean false hits
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    return string.format("transform_boolean(%q)", s)
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local function cb()
                return false
            end

            local data, err = cache:get("key", nil, cb)
            if not data then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(data)
        }
    }
--- response_body
transform_boolean("false")
--- no_error_log
[error]



=== TEST 7: l1_serializer is called on lock timeout
--- config
    location /t {
        content_by_lua_block {
            -- insert 2 dummy values to ensure that lock acquisition (which
            -- uses shm:set) will _not_ evict out stale cached value
            ngx.shared.cache_shm:set(1, true, 0.2)
            ngx.shared.cache_shm:set(2, true, 0.2)

            local mlcache = require "resty.mlcache"
            local cache_1 = assert(mlcache.new("my_mlcache", "cache_shm", {
                ttl = 0.3,
                resurrect_ttl = 0.3,
                l1_serializer = function(s)
                    return "from cache_1"
                end,
            }))
            local cache_2 = assert(mlcache.new("my_mlcache", "cache_shm", {
                ttl = 0.3,
                resurrect_ttl = 0.3,
                l1_serializer = function(s)
                    return "from cache_2"
                end,
                resty_lock_opts = {
                    timeout = 0.2
                }
            }))

            local function cb(delay, return_val)
                if delay then
                    ngx.sleep(delay)
                end

                return return_val or 123
            end

            -- cache in shm

            local data, err, hit_lvl = cache_1:get("my_key", nil, cb)
            assert(data == "from cache_1")
            assert(err == nil)
            assert(hit_lvl == 3)

            -- make shm + LRU expire

            ngx.sleep(0.3)

            local t1 = ngx.thread.spawn(function()
                -- trigger L3 callback again, but slow to return this time

                cache_1:get("my_key", nil, cb, 0.3, 456)
            end)

            local t2 = ngx.thread.spawn(function()
                -- make this mlcache wait on other's callback, and timeout

                local data, err, hit_lvl = cache_2:get("my_key", nil, cb)
                ngx.say("data: ", data)
                ngx.say("err: ", err)
                ngx.say("hit_lvl: ", hit_lvl)
            end)

            assert(ngx.thread.wait(t1))
            assert(ngx.thread.wait(t2))

            ngx.say()
            ngx.say("-> subsequent get()")
            data, err, hit_lvl = cache_2:get("my_key", nil, cb, nil, 123)
            ngx.say("data: ", data)
            ngx.say("err: ", err)
            ngx.say("hit_lvl: ", hit_lvl) -- should be 1 since LRU instances are shared by mlcache namespace, and t1 finished
        }
    }
--- response_body
data: from cache_2
err: nil
hit_lvl: 4

-> subsequent get()
data: from cache_1
err: nil
hit_lvl: 1
--- error_log eval
qr/\[warn\] .*? could not acquire callback lock: timeout/



=== TEST 8: l1_serializer is called when value has < 1ms remaining_ttl
--- config
    location /t {
        content_by_lua_block {
            local forced_now = ngx.now()
            ngx.now = function()
                return forced_now
            end

            local mlcache = require "resty.mlcache"

            local cache = assert(mlcache.new("my_mlcache", "cache_shm", {
                ttl = 0.2,
                l1_serializer = function(s)
                    return "override"
                end,
            }))

            local function cb(v)
                return v or 42
            end

            local data, err = cache:get("key", nil, cb)
            assert(data == "override", err or "invalid data value: " .. data)

            -- drop L1 cache value
            cache.lru:delete("key")

            -- advance 0.2 second in the future, and simulate another :get()
            -- call; the L2 shm entry will still be alive (as its clock is
            -- not faked), but mlcache will compute a remaining_ttl of 0;
            -- In such cases, we should _not_ cache the value indefinitely in
            -- the L1 LRU cache.
            forced_now = forced_now + 0.2

            local data, err, hit_lvl = cache:get("key", nil, cb)
            assert(data == "override", err or "invalid data value: " .. data)

            ngx.say("+0.200s hit_lvl: ", hit_lvl)

            -- the value is not cached in LRU (too short ttl anyway)

            data, err, hit_lvl = cache:get("key", nil, cb)
            assert(data == "override", err or "invalid data value: " .. data)

            ngx.say("+0.200s hit_lvl: ", hit_lvl)

            -- make it expire in shm (real wait)
            ngx.sleep(0.201)

            data, err, hit_lvl = cache:get("key", nil, cb, 91)
            assert(data == "override", err or "invalid data value: " .. data)

            ngx.say("+0.201s hit_lvl: ", hit_lvl)
        }
    }
--- response_body
+0.200s hit_lvl: 2
+0.200s hit_lvl: 2
+0.201s hit_lvl: 3
--- no_error_log
[error]



=== TEST 9: l1_serializer is called in protected mode (L2 miss)
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    error("cannot transform")
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("key", nil, function() return "foo" end)
            if not data then
                ngx.say(err)
            end

            ngx.say(data)
        }
    }
--- response_body_like
l1_serializer threw an error: .*?: cannot transform
--- no_error_log
[error]



=== TEST 10: l1_serializer is called in protected mode (L2 hit)
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local called = false
            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    if called then error("cannot transform") end
                    called = true
                    return string.format("transform(%q)", s)
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            assert(cache:get("key", nil, function() return "foo" end))
            cache.lru:delete("key")

            local data, err = cache:get("key", nil, function() return "foo" end)
            if not data then
                ngx.say(err)
            end

            ngx.say(data)
        }
    }
--- response_body_like
l1_serializer threw an error: .*?: cannot transform
--- no_error_log
[error]



=== TEST 11: l1_serializer is not called for L2+L3 misses (no record)
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local called = false
            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    called = true
                    return string.format("transform(%s)", s)
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("key", nil, function() return nil end)
            if data ~= nil then
                ngx.log(ngx.ERR, "got a value for a L3 miss: ", tostring(data))
                return
            elseif err ~= nil then
                ngx.log(ngx.ERR, "got an error for a L3 miss: ", tostring(err))
                return
            end

            -- our L3 returned nil, we do not call the l1_serializer and
            -- we store the LRU nil sentinel value

            ngx.say("l1_serializer called for L3 miss: ", called)

            -- delete from LRU, and try from L2 again

            cache.lru:delete("key")

            local data, err = cache:get("key", nil, function() error("not supposed to call") end)
            if data ~= nil then
                ngx.log(ngx.ERR, "got a value for a L3 miss: ", tostring(data))
                return
            elseif err ~= nil then
                ngx.log(ngx.ERR, "got an error for a L3 miss: ", tostring(err))
                return
            end

            ngx.say("l1_serializer called for L2 negative hit: ", called)
        }
    }
--- response_body
l1_serializer called for L3 miss: false
l1_serializer called for L2 negative hit: false
--- no_error_log
[error]



=== TEST 12: l1_serializer is not supposed to return a nil value
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    return nil
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = cache:get("key", nil, function() return "foo" end)
            assert(not ok, "get() should not return successfully")
            ngx.say(err)
        }
    }
--- response_body_like
l1_serializer returned a nil value
--- no_error_log
[error]



=== TEST 13: l1_serializer can return nil + error
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    return nil, "l1_serializer: cannot transform"
                end,
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("key", nil, function() return "foo" end)
            if not data then
                ngx.say(err)
            end

            ngx.say("data: ", data)
        }
    }
--- response_body
l1_serializer: cannot transform
data: nil
--- no_error_log
[error]



=== TEST 14: l1_serializer can be given as a get() argument
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("key", {
                l1_serializer = function(s)
                    return string.format("transform(%q)", s)
                end
            }, function() return "foo" end)
            if not data then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(data)
        }
    }
--- response_body
transform("foo")
--- no_error_log
[error]



=== TEST 15: l1_serializer as get() argument has precedence over the constructor one
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                l1_serializer = function(s)
                    return string.format("constructor(%q)", s)
                end
            })

            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = cache:get("key1", {
                l1_serializer = function(s)
                    return string.format("get_argument(%q)", s)
                end
            }, function() return "foo" end)
            if not data then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(data)

            local data, err = cache:get("key2", nil, function() return "bar" end)
            if not data then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(data)
        }
    }
--- response_body
get_argument("foo")
constructor("bar")
--- no_error_log
[error]



=== TEST 16: get() validates l1_serializer is a function
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm")
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = pcall(cache.get, cache, "key", {
                l1_serializer = false,
            }, function() return "foo" end)
            if not data then
                ngx.say(err)
            end
        }
    }
--- response_body
opts.l1_serializer must be a function
--- no_error_log
[error]



=== TEST 17: set() calls l1_serializer
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
                l1_serializer = function(s)
                    return string.format("transform(%q)", s)
                end
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = cache:set("key", nil, "value")
            if not ok then
                ngx.log(ngx.ERR, err)
                return
            end

            local value, err = cache:get("key", nil, error)
            if not value then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(value)
        }
    }
--- response_body
transform("value")
--- no_error_log
[error]



=== TEST 18: set() calls l1_serializer for boolean false values
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
                l1_serializer = function(s)
                    return string.format("transform_boolean(%q)", s)
                end
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = cache:set("key", nil, false)
            if not ok then
                ngx.log(ngx.ERR, err)
                return
            end

            local value, err = cache:get("key", nil, error)
            if not value then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(value)
        }
    }
--- response_body
transform_boolean("false")
--- no_error_log
[error]



=== TEST 19: l1_serializer as set() argument has precedence over the constructor one
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
                l1_serializer = function(s)
                    return string.format("constructor(%q)", s)
                end
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = cache:set("key", {
                l1_serializer = function(s)
                    return string.format("set_argument(%q)", s)
                end
            }, "value")
            if not ok then
                ngx.log(ngx.ERR, err)
                return
            end

            local value, err = cache:get("key", nil, error)
            if not value then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(value)
        }
    }
--- response_body
set_argument("value")
--- no_error_log
[error]



=== TEST 20: set() validates l1_serializer is a function
--- config
    location /t {
        content_by_lua_block {
            local mlcache = require "resty.mlcache"

            local cache, err = mlcache.new("my_mlcache", "cache_shm", {
                ipc_shm = "ipc_shm",
            })
            if not cache then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = pcall(cache.set, cache, "key", {
                l1_serializer = true
            }, "value")
            if not data then
                ngx.say(err)
            end
        }
    }
--- response_body
opts.l1_serializer must be a function
--- no_error_log
[error]
