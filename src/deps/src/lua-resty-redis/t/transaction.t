# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

run_tests();

__DATA__

=== TEST 1: sanity
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local cjson = require "cjson"
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local redis_key = "foo"

            local ok, err = red:multi()
            if not ok then
                ngx.say("failed to run multi: ", err)
                return
            end

            ngx.say("multi ans: ", cjson.encode(ok))

            local ans, err = red:sort("log", "by", redis_key .. ":*->timestamp")
            if not ans then
                ngx.say("failed to run sort: ", err)
                return
            end

            ngx.say("sort ans: ", cjson.encode(ans))

            ans, err = red:exec()

            ngx.say("exec ans: ", cjson.encode(ans))

            local ok, err = red:set_keepalive(0, 1024)
            if not ok then
                ngx.say("failed to put the current redis connection into pool: ", err)
                return
            end
        ';
--- response_body
multi ans: "OK"
sort ans: "QUEUED"
exec ans: [{}]
--- no_error_log
[error]



=== TEST 2: redis cmd reference sample: redis does not halt on errors
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local cjson = require "cjson"
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local ok, err = red:multi()
            if not ok then
                ngx.say("failed to run multi: ", err)
                return
            end

            ngx.say("multi ans: ", cjson.encode(ok))

            local ans, err = red:set("a", "abc")
            if not ans then
                ngx.say("failed to run sort: ", err)
                return
            end

            ngx.say("set ans: ", cjson.encode(ans))

            local ans, err = red:lpop("a")
            if not ans then
                ngx.say("failed to run sort: ", err)
                return
            end

            ngx.say("set ans: ", cjson.encode(ans))

            ans, err = red:exec()

            ngx.say("exec ans: ", cjson.encode(ans))

            red:close()
        ';
--- response_body_like chop
^multi ans: "OK"
set ans: "QUEUED"
set ans: "QUEUED"
exec ans: \["OK",\[false,"(?:ERR|WRONGTYPE) Operation against a key holding the wrong kind of value"\]\]
$
--- no_error_log
[error]
