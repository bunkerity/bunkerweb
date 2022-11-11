# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

log_level 'warn';

run_tests();

__DATA__

=== TEST 1: github issue #108: ngx.location.capture + redis.set_keepalive
--- http_only
--- http_config eval: $::GlobalConfig
--- config
    location /r1 {
        default_type text/html;
        set $port $TEST_NGINX_REDIS_PORT;
        #lua_code_cache off;
        lua_need_request_body on;
        content_by_lua_file html/r1.lua;
    }

    location /r2 {
        default_type text/html;
        set $port $TEST_NGINX_REDIS_PORT;
        #lua_code_cache off;
        lua_need_request_body on;
        content_by_lua_file html/r2.lua;
    }

    location /anyurl {
        internal;
        proxy_pass http://127.0.0.1:$server_port/dummy;
    }

    location = /dummy {
        echo dummy;
    }
--- user_files
>>> r1.lua
local redis = require "resty.redis"
local red = redis:new()
local ok, err = red:connect("127.0.0.1", ngx.var.port)
if not ok then
    ngx.say("failed to connect: ", err)
    return
end
local ok, err = red:flushall()
if not ok then
    ngx.say("failed to flushall: ", err)
    return
end
ok, err = red:set_keepalive()
if not ok then
    ngx.say("failed to set keepalive: ", err)
    return
end
local http_ress = ngx.location.capture("/r2") -- 1
ngx.say("ok")

>>> r2.lua
local redis = require "resty.redis"
local red = redis:new()
local ok, err = red:connect("127.0.0.1", ngx.var.port) --2
if not ok then
    ngx.say("failed to connect: ", err)
    return
end
local res = ngx.location.capture("/anyurl") --3
--- request
    GET /r1
--- response_body
ok
--- no_error_log
[error]



=== TEST 2: exit(404) after I/O (ngx_lua github issue #110
https://github.com/chaoslawful/lua-nginx-module/issues/110
--- http_only
--- http_config eval: $::GlobalConfig
--- config
    error_page 400 /400.html;
    error_page 404 /404.html;
    location /foo {
        access_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(2000) -- 2 sec

            -- ngx.log(ngx.ERR, "hello");

            -- or connect to a unix domain socket file listened
            -- by a redis server:
            --     local ok, err = red:connect("unix:/path/to/redis.sock")

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
                return
            end

            res, err = red:set("dog", "an animal")
            if not res then
                ngx.log(ngx.ERR, "failed to set dog: ", err)
                return
            end

            -- ngx.say("set dog: ", res)

            local res, err = red:get("dog")
            if err then
                ngx.log(ngx.ERR, "failed to get dog: ", err)
                return
            end

            if not res then
                ngx.log(ngx.ERR, "dog not found.")
                return
            end

            -- ngx.say("dog: ", res)

            -- red:close()
            local ok, err = red:set_keepalive(0, 100)
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            ngx.exit(404)
        ';
        echo Hello;
    }
--- user_files
>>> 400.html
Bad request, dear...
>>> 404.html
Not found, dear...
--- request
    GET /foo
--- response_body
Not found, dear...
--- error_code: 404
--- no_error_log
[error]



=== TEST 3: set and get an empty string
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            -- or connect to a unix domain socket file listened
            -- by a redis server:
            --     local ok, err = red:connect("unix:/path/to/redis.sock")

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            res, err = red:set("dog", "")
            if not res then
                ngx.say("failed to set dog: ", err)
                return
            end

            ngx.say("set dog: ", res)

            for i = 1, 2 do
                local res, err = red:get("dog")
                if err then
                    ngx.say("failed to get dog: ", err)
                    return
                end

                if not res then
                    ngx.say("dog not found.")
                    return
                end

                ngx.say("dog: ", res)
            end

            red:close()
        ';
--- response_body
set dog: OK
dog: 
dog: 
--- no_error_log
[error]



=== TEST 4: ngx.exec() after red:get()
--- http_only
--- http_config eval: $::GlobalConfig
--- config
    location /t {
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000) -- 1 sec

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local res, err = red:get("dog")
            if err then
                ngx.say("failed to get dog: ", err)
                return
            end

            ngx.exec("/hello")
        ';
    }

    location = /hello {
        echo hello world;
    }

--- request
    GET /t
--- response_body
hello world
--- no_error_log
[error]
