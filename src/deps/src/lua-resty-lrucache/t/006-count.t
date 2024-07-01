# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestLRUCache;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

no_long_string();
run_tests();

__DATA__

=== TEST 1: count() returns current cache size
--- config
    location = /t {
        content_by_lua_block {
            local lrucache = require "resty.lrucache"
            local c = lrucache.new(2)

            ngx.say("count: ", c:count())

            c:set("dog", 32)
            ngx.say("count: ", c:count())
            c:set("dog", 33)

            ngx.say("count: ", c:count())
            c:set("cat", 33)

            ngx.say("count: ", c:count())
            c:set("pig", 33)

            ngx.say("count: ", c:count())
            c:delete("dog")

            ngx.say("count: ", c:count())
            c:delete("pig")

            ngx.say("count: ", c:count())
            c:delete("cat")

            ngx.say("count: ", c:count())
        }
    }
--- response_body
count: 0
count: 1
count: 1
count: 2
count: 2
count: 2
count: 1
count: 0
