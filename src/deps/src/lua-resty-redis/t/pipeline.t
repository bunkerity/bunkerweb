# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

run_tests();

__DATA__

=== TEST 1: basic
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            for i = 1, 2 do
                red:init_pipeline()

                red:set("dog", "an animal")
                red:get("dog")
                red:set("dog", "hello")
                red:get("dog")

                local results = red:commit_pipeline()
                local cjson = require "cjson"
                ngx.say(cjson.encode(results))
            end

            red:close()
        ';
--- response_body
["OK","an animal","OK","hello"]
["OK","an animal","OK","hello"]
--- no_error_log
[error]



=== TEST 2: cancel automatically
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            red:init_pipeline()

            red:set("dog", "an animal")
            red:get("dog")

            for i = 1, 2 do
                red:init_pipeline()

                red:set("dog", "an animal")
                red:get("dog")
                red:set("dog", "hello")
                red:get("dog")

                local results = red:commit_pipeline()
                local cjson = require "cjson"
                ngx.say(cjson.encode(results))
            end

            red:close()
        ';
--- response_body
["OK","an animal","OK","hello"]
["OK","an animal","OK","hello"]
--- no_error_log
[error]



=== TEST 3: cancel explicitly
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            red:init_pipeline()

            red:set("dog", "an animal")
            red:get("dog")

            red:cancel_pipeline()

            local res, err = red:flushall()
            if not res then
                ngx.say("failed to flush all: ", err)
                return
            end

            ngx.say("flushall: ", res)

            for i = 1, 2 do
                red:init_pipeline()

                red:set("dog", "an animal")
                red:get("dog")
                red:set("dog", "hello")
                red:get("dog")

                local results = red:commit_pipeline()
                local cjson = require "cjson"
                ngx.say(cjson.encode(results))
            end

            red:close()
        ';
--- response_body
flushall: OK
["OK","an animal","OK","hello"]
["OK","an animal","OK","hello"]
--- no_error_log
[error]



=== TEST 4: mixed
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", 6379)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            res, err = red:set("dog", "an aniaml")
            if not ok then
                ngx.say("failed to set dog: ", err)
                return
            end

            ngx.say("set result: ", res)

            local res, err = red:get("dog")
            if not res then
                ngx.say("failed to get dog: ", err)
                return
            end

            if res == ngx.null then
                ngx.say("dog not found.")
                return
            end

            ngx.say("dog: ", res)

            red:init_pipeline()
            red:set("cat", "Marry")
            red:set("horse", "Bob")
            red:get("cat")
            red:get("horse")
            local results, err = red:commit_pipeline()
            if not results then
                ngx.say("failed to commit the pipelined requests: ", err)
                return
            end

            for i, res in ipairs(results) do
                if type(res) == "table" then
                    if res[1] == false then
                        ngx.say("failed to run command ", i, ": ", res[2])
                    else
                        ngx.say("cmd ", i, ": ", res)
                    end
                else
                    -- process the scalar value
                    ngx.say("cmd ", i, ": ", res)
                end
            end

            -- put it into the connection pool of size 100,
            -- with 0 idle timeout
            local ok, err = red:set_keepalive(0, 100)
            if not ok then
                ngx.say("failed to set keepalive: ", err)
                return
            end

            -- or just close the connection right away:
            -- local ok, err = red:close()
            -- if not ok then
            --     ngx.say("failed to close: ", err)
            --     return
            -- end
        ';
--- response_body
set result: OK
dog: an aniaml
cmd 1: OK
cmd 2: OK
cmd 3: Marry
cmd 4: Bob
--- no_error_log
[error]



=== TEST 5: redis return error in pipeline
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", 6379)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local res, err = red:del("dog")
            if not res then
                ngx.say("failed to del dog: ", err)
                return
            end

            red:init_pipeline()
            red:hkeys("dog")
            red:set("dog", "an animal")
            red:hkeys("dog")
            red:get("dog")
            local results, err = red:commit_pipeline()
            if not results then
                ngx.say("failed to commit the pipelined requests: ", err)
                return
            end

            for i, res in ipairs(results) do
                if type(res) == "table" then
                    if res[1] == false then
                        ngx.say("failed to run command ", i, ": ", res[2])
                    else
                        ngx.say("cmd ", i, ": ", res)
                    end
                else
                    -- process the scalar value
                    ngx.say("cmd ", i, ": ", res)
                end
            end

            -- put it into the connection pool of size 100,
            -- with 0 idle timeout
            local ok, err = red:set_keepalive(0, 100)
            if not ok then
                ngx.say("failed to set keepalive: ", err)
                return
            end
        ';
--- response_body
cmd 1: 
cmd 2: OK
failed to run command 3: WRONGTYPE Operation against a key holding the wrong kind of value
cmd 4: an animal
--- no_error_log
[error]
