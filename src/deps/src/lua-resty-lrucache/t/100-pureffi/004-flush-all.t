# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestLRUCache;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

no_long_string();
run_tests();

__DATA__

=== TEST 1: flush_all() deletes all keys (cache partial occupied)
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"

            local N = 4

            local c = lrucache.new(N)

            for i = 1, N / 2 do
                c:set("key " .. i, i)
            end

            c:flush_all()

            for i = 1, N do
                local key = "key " .. i
                local v = c:get(key)
                ngx.say(i, ": ", v)
            end

            ngx.say("++")

            for i = 1, N + 1 do
                c:set("key " .. i, i)
            end

            for i = 1, N + 1 do
                ngx.say(i, ": ", (c:get("key " .. i)))
            end
        }
    }
--- response_body
1: nil
2: nil
3: nil
4: nil
++
1: nil
2: 2
3: 3
4: 4
5: 5



=== TEST 2: flush_all() deletes all keys (cache fully occupied)
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"

            local N = 4

            local c = lrucache.new(N)

            for i = 1, N + 1 do
                c:set("key " .. i, i)
            end

            ngx.say(c:count())
            c:flush_all()
            ngx.say(c:count())

            for i = 1, N + 1 do
                local key = "key " .. i
                local v = c:get(key)
                ngx.say(i, ": ", v)
            end

            ngx.say("++")

            for i = 1, N + 1 do
                c:set("key " .. i, i)
            end

            for i = 1, N + 1 do
                ngx.say(i, ": ", (c:get("key " .. i)))
            end
        }
    }
--- response_body
4
0
1: nil
2: nil
3: nil
4: nil
5: nil
++
1: nil
2: 2
3: 3
4: 4
5: 5



=== TEST 3: flush_all() flush empty cache store
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache.pureffi"

            local N = 4

            local c = lrucache.new(4)

            c:flush_all()

            for i = 1, N do
                local key = "key " .. i
                local v = c:get(key)
                ngx.say(i, ": ", v)
            end

            ngx.say("++")

            for i = 1, N + 1 do
                c:set("key " .. i, i)
            end

            for i = 1, N + 1 do
                ngx.say(i, ": ", (c:get("key " .. i)))
            end
        }
    }
--- response_body
1: nil
2: nil
3: nil
4: nil
++
1: nil
2: 2
3: 3
4: 4
5: 5
