# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestLRUCache;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

no_long_string();
run_tests();

__DATA__

=== TEST 1: should-store-false
--- config
    location = /t {
        content_by_lua '
            local lrucache = require "resty.lrucache.pureffi"
            local c = lrucache.new(2)

            collectgarbage()

            c:set("false-value", false)
            ngx.say("false-value: ", (c:get("false-value")))

            c:delete("false-value")
            ngx.say("false-value: ", (c:get("false-value")))
        ';
    }
--- response_body
false-value: false
false-value: nil
