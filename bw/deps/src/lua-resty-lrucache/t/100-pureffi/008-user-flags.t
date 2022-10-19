# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestLRUCache;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

no_long_string();
run_tests();

__DATA__

=== TEST 1: no user flags by default
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(2)

            c:set("dog", 32)
            c:set("cat", 56)

            local v, err, flags = c:get("dog")
            ngx.say("dog: ", v, " ", err, " ", flags)

            local v, err, flags = c:get("cat")
            ngx.say("cat: ", v, " ", err, " ", flags)
        }
    }
--- response_body
dog: 32 nil 0
cat: 56 nil 0



=== TEST 2: stores user flags if specified
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(2)

            c:set("dog", 32, nil, 0x01)
            c:set("cat", 56, nil, 0x02)

            local v, err, flags = c:get("dog")
            ngx.say("dog: ", v, " ", err, " ", flags)

            local v, err, flags = c:get("cat")
            ngx.say("cat: ", v, " ", err, " ", flags)
        }
    }
--- response_body
dog: 32 nil 1
cat: 56 nil 2



=== TEST 3: user flags cannot be negative
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(3)

            c:set("dog", 32, nil, 0)
            c:set("cat", 56, nil, -1)

            local v, err, flags = c:get("dog")
            ngx.say("dog: ", v, " ", err, " ", flags)

            local v, err, flags = c:get("cat")
            ngx.say("cat: ", v, " ", err, " ", flags)
        }
    }
--- response_body
dog: 32 nil 0
cat: 56 nil 0



=== TEST 4: user flags not number is ignored
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(2)

            c:set("dog", 32, nil, "")

            local v, err, flags = c:get("dog")
            ngx.say(v, " ", err, " ", flags)
        }
    }
--- response_body
32 nil 0



=== TEST 5: all nodes from double-ended queue have flags
--- config
    location = /t {
        content_by_lua_block {
            local len = 10

            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(len)

            for i = 1, len do
                c:set(i, 32, nil, 1)
            end

            for i = 1, len do
                local v, _, flags = c:get(i)
                if not flags then
                    ngx.say("item ", i, " does not have flags")
                    return
                end
            end

            ngx.say("ok")
        }
    }
--- response_body
ok



=== TEST 6: user flags are preserved when item is stale
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1)

            c:set("dogs", 32, 0.2, 3)
            ngx.sleep(0.21)

            local v, err, flags = c:get("dogs")
            ngx.say(v, " ", err, " ", flags)
        }
    }
--- response_body
nil 32 3



=== TEST 7: user flags are not preserved upon eviction
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1)

            for i = 1, 10 do
                local flags = i % 2 == 0 and i
                c:set(i, true, nil, flags)

                local v, err, flags = c:get(i)
                ngx.say(v, " ", err, " ", flags)
            end
        }
    }
--- response_body
true nil 0
true nil 2
true nil 0
true nil 4
true nil 0
true nil 6
true nil 0
true nil 8
true nil 0
true nil 10
