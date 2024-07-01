# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

run_tests();

__DATA__

=== TEST 1: sanity
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua_block {
            local cjson = require "cjson"
            local redis = require "resty.redis"
            redis.register_module_prefix("bf")
            redis.register_module_prefix("test")

            local red = redis:new()

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local res, err = red:del("module_1")
            if not res then
                ngx.say(err)
                return
            end

            res, err = red:bf():add("module_1", 1)
            if not res then
                ngx.say(err)
                return
            end
            ngx.say("receive: ", cjson.encode(res))

            res, err = red:bf():exists("module_1", 1)
            if not res then
                ngx.say(err)
                return
            end
            ngx.say("receive: ", cjson.encode(res))

            -- call normal command
            res, err = red:del("module_1")
            if not res then
                ngx.say(err)
                return
            end
            ngx.say("receive: ", cjson.encode(res))

            -- call cached 'exists' again
            res, err = red:exists("module_1")
            if not res then
                ngx.say(err)
                return
            end
            ngx.say("receive: ", cjson.encode(res))

            -- call pre-created 'get' method
            res, err = red:test():get()
            if not res then
                ngx.say(err)
            end

            red:close()
        }
--- response_body_like
receive: 1
receive: 1
receive: 1
receive: 0
ERR unknown command `test.get`.+
--- no_error_log
[error]
