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
            local lrucache = require "resty.lrucache.pureffi"
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
            local lrucache = require "resty.lrucache.pureffi"
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
            local lrucache = require "resty.lrucache.pureffi"
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
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1)

            c:set("dog", 32, 0.6)
            ngx.say("dog: ", (c:get("dog")))

            ngx.sleep(0.3)
            ngx.say("dog: ", (c:get("dog")))

            ngx.sleep(0.31)
            local v, err = c:get("dog")
            ngx.say("dog: ", v, " ", err)
        ';
    }
--- response_body
dog: 32
dog: 32
dog: nil 32



=== TEST 5: load factor
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1, 0.25)

            ngx.say(c.bucket_sz)
        ';
    }
--- response_body
4



=== TEST 6: load factor clamped to 0.1
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(3, 0.05)

            ngx.say(c.bucket_sz)
        ';
    }
--- response_body
32



=== TEST 7: load factor saturated to 1
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(3, 2.1)

            ngx.say(c.bucket_sz)
        ';
    }
--- response_body
4



=== TEST 8: non-string keys
--- config
    location = /t {
        content_by_lua '
            local function log(...)
                ngx.say(...)
            end

            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(2)

            collectgarbage()

            local tab1 = {1, 2}
            local tab2 = {3, 4}

            c:set(tab1, 32)
            c:set(tab2, 56)
            log("tab1: ", (c:get(tab1)))
            log("tab2: ", (c:get(tab2)))

            c:set(tab1, 32)
            c:set(tab2, 56)
            log("tab1: ", (c:get(tab1)))
            log("tab2: ", (c:get(tab2)))

            c:delete(tab1)
            c:delete(tab2)
            log("tab1: ", (c:get(tab1)))
            log("tab2: ", (c:get(tab2)))
        ';
    }
--- response_body
tab1: 32
tab2: 56
tab1: 32
tab2: 56
tab1: nil
tab2: nil



=== TEST 9: replace value
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
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



=== TEST 10: replace value 2
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1)

            c:set("dog", 32, 1.0)
            ngx.say("dog: ", (c:get("dog")))

            c:set("dog", 33, 0.3)
            ngx.say("dog: ", (c:get("dog")))

            ngx.sleep(0.4)
            local v, err = c:get("dog")
            ngx.say("dog: ", v, " ", err)
        ';
    }
--- response_body
dog: 32
dog: 33
dog: nil 33



=== TEST 11: replace value 3 (the old value has longer expire time)
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1)

            c:set("dog", 32, 1.2)
            c:set("dog", 33, 0.6)
            ngx.sleep(0.2)
            ngx.say("dog: ", (c:get("dog")))

            ngx.sleep(0.5)
            local v, err = c:get("dog")
            ngx.say("dog: ", v, " ", err)
        ';
    }
--- response_body
dog: 33
dog: nil 33



=== TEST 12: replace value 4
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(1)

            c:set("dog", 32, 0.1)
            ngx.sleep(0.2)

            c:set("dog", 33)
            ngx.sleep(0.2)
            ngx.say("dog: ", (c:get("dog")))
        ';
    }
--- response_body
dog: 33
