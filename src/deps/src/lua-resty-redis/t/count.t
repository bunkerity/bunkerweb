# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

run_tests();

__DATA__

=== TEST 1: module size of resty.redis
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            n = 0
            for _, _ in pairs(redis) do
                n = n + 1
            end
            ngx.say("size: ", n)
        ';
--- response_body
size: 56
--- no_error_log
[error]
