# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestLRUCache;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache"
            local c = lrucache.new(2)

            collectgarbage()

            c:set("dog", 32)
            c:set("cat", 56)
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))

            c:set("dog", 32)
            c:set("cat", 56)
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))

            c:delete("dog")
            c:delete("cat")
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))
        ';
    }
--- response_body
dog: 32
cat: 56
dog: 32
cat: 56
dog: nil
cat: nil



=== TEST 2: evict existing items
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache"
            local c = lrucache.new(2)
            if not c then
               ngx.say("failed to init lrucace: ", err)
               return
            end

            c:set("dog", 32)
            c:set("cat", 56)
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))

            c:set("bird", 76)
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))
            ngx.say("bird: ", (c:get("bird")))
        ';
    }
--- response_body
dog: 32
cat: 56
dog: nil
cat: 56
bird: 76



=== TEST 3: evict existing items (reordered, get should also count)
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache"
            local c = lrucache.new(2)
            if not c then
               ngx.say("failed to init lrucace: ", err)
               return
            end

            c:set("cat", 56)
            c:set("dog", 32)
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))

            c:set("bird", 76)
            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))
            ngx.say("bird: ", (c:get("bird")))
        ';
    }
--- response_body
dog: 32
cat: 56
dog: nil
cat: 56
bird: 76



=== TEST 4: ttl
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache"
            local c = lrucache.new(1)

            c:set("dog", 32, 0.5)
            ngx.say("dog: ", (c:get("dog")))

            ngx.sleep(0.25)
            ngx.say("dog: ", (c:get("dog")))

            ngx.sleep(0.26)
            local v, err = c:get("dog")
            ngx.say("dog: ", v, " ", err)
        ';
    }
--- response_body
dog: 32
dog: 32
dog: nil 32



=== TEST 5: ttl
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache"
            local lim = 5
            local c = lrucache.new(lim)
            local n = 1000

            for i = 1, n do
                c:set("dog" .. i, i)
                c:delete("dog" .. i)
                c:set("dog" .. i, i)
                local cnt = 0
                for k, v in pairs(c.hasht) do
                    cnt = cnt + 1
                end
                assert(cnt <= lim)
            end

            for i = 1, n do
                local key = "dog" .. math.random(1, n)
                c:get(key)
            end

            for i = 1, n do
                local key = "dog" .. math.random(1, n)
                c:get(key)
                c:set("dog" .. i, i)

                local cnt = 0
                for k, v in pairs(c.hasht) do
                    cnt = cnt + 1
                end
                assert(cnt <= lim)
            end

            ngx.say("ok")
        ';
    }
--- response_body
ok
--- timeout: 20



=== TEST 6: replace value
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache"
            local c = lrucache.new(1)

            c:set("dog", 32)
            ngx.say("dog: ", (c:get("dog")))

            c:set("dog", 33)
            ngx.say("dog: ", (c:get("dog")))
        ';
    }
--- response_body
dog: 32
dog: 33
