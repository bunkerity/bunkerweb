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

            local lrucache = require "resty.lrucache.pureffi"
            local c2 = lrucache.new(2)

            ngx.say("dog: ", (c2:get("dog")))
            ngx.say("cat: ", (c2:get("cat")))

            c2:set("dog", 9)
            c2:set("cat", "hi")

            ngx.say("dog: ", (c2:get("dog")))
            ngx.say("cat: ", (c2:get("cat")))

            ngx.say("dog: ", (c:get("dog")))
            ngx.say("cat: ", (c:get("cat")))
        ';
    }
--- response_body
dog: 32
cat: 56
dog: nil
cat: nil
dog: 9
cat: hi
dog: 32
cat: 56
