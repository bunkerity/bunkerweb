# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

run_tests();

__DATA__

=== TEST 1: single channel
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local cjson = require "cjson"
            local redis = require "resty.redis"

            redis.add_commands("foo", "bar")

            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local res, err = red:foo("a")
            if not res then
                ngx.say("failed to foo: ", err)
            end

            res, err = red:bar()
            if not res then
                ngx.say("failed to bar: ", err)
            end
        ';
--- response_body eval
qr/\Afailed to foo: ERR unknown command [`']foo[`'](?:, with args beginning with: `a`,\s*)?
failed to bar: ERR unknown command [`']bar[`'](?:, with args beginning with:\s*)?
\z/
--- no_error_log
[error]
