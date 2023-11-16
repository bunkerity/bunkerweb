# vim:set ft= ts=4 sw=4 et:
use Test::Nginx::Socket::Lua;
use Cwd qw(cwd);

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();
$ENV{TEST_NGINX_REDIS_PORT} ||= 6379;
$ENV{TEST_NGINX_STREAM_REDIS_PORT} ||= 12345;

my $MainConfig = qq{
    stream {
        server {
            listen unix:$ENV{TEST_NGINX_HTML_DIR}/nginx.sock;
            listen unix:$ENV{TEST_NGINX_HTML_DIR}/nginx-ssl.sock ssl;
            listen 127.0.0.1:$ENV{TEST_NGINX_STREAM_REDIS_PORT} ssl;

            ssl_certificate ../../cert/test.crt;
            ssl_certificate_key ../../cert/test.key;

            proxy_pass 127.0.0.1:$ENV{TEST_NGINX_REDIS_PORT};
        }
    }
};

my $pwd = cwd();
my $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;;";
};

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->main_config) {
        $block->set_value("main_config", $MainConfig);
    }

    if (!defined $block->http_config) {
        $block->set_value("http_config", $HttpConfig);
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }

    if (!defined $block->no_error_log) {
        $block->set_value("no_error_log", "[error]");
    }
});

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: ssl connection on non ssl server
--- config
    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(100)

            local ok, err = red:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock", {
                ssl = true
            })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end
        }
    }
--- response_body
failed to connect: failed to do ssl handshake: timeout



=== TEST 2: set and get on ssl connection
--- config
    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000)

            local ok, err = red:connect("127.0.0.1", $TEST_NGINX_STREAM_REDIS_PORT, {
                ssl = true
            })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ok, err = red:select(1)
            if not ok then
                ngx.say("failed to select: ", err)
                return
            end

            local res, err = red:set("dog", "an animal")
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
        }
    }
--- response_body
set dog: OK
dog: an animal
dog: an animal



=== TEST 3: set and get on ssl connection via unix socket
--- config
    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(1000)

            local ok, err = red:connect("unix:$TEST_NGINX_HTML_DIR/nginx-ssl.sock", {
                ssl = true
            })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ok, err = red:select(1)
            if not ok then
                ngx.say("failed to select: ", err)
                return
            end

            local res, err = red:set("dog", "an animal")
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
        }
    }
--- response_body
set dog: OK
dog: an animal
dog: an animal



=== TEST 4: ssl connection with ssl_verify (without CA)
--- config
    lua_socket_log_errors off;

    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(100)

            local ok, err = red:connect("unix:$TEST_NGINX_HTML_DIR/nginx-ssl.sock", {
                ssl = true,
                ssl_verify = true
            })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end
        }
    }
--- response_body
failed to connect: failed to do ssl handshake: 18: self signed certificate



=== TEST 5: ssl connection with ssl_verify (with CA)
--- config
    lua_socket_log_errors off;
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(100)

            local ok, err = red:connect("unix:$TEST_NGINX_HTML_DIR/nginx-ssl.sock", {
                ssl = true,
                ssl_verify = true
            })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("ok")
        }
    }
--- response_body
ok



=== TEST 6: non-ssl connection to unix socket (issue #187)
--- config
    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(100)

            local ok, err = red:connect("unix:$TEST_NGINX_HTML_DIR/nginx-ssl.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("ok")
        }
    }
--- response_body
ok



=== TEST 7: non-ssl connection to unix socket with second argument nil (issue #187)
--- config
    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()

            red:set_timeout(100)

            local ok, err = red:connect("unix:$TEST_NGINX_HTML_DIR/nginx-ssl.sock",nil)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("ok")
        }
    }
--- response_body
ok



=== TEST 8: ssl reuse
--- config
    location /t {
        content_by_lua_block {
            local redis = require "resty.redis"
            local red = redis:new()
            red:set_timeout(1000)

            local function connect_set(red)
                local ok, err = red:connect("127.0.0.1", $TEST_NGINX_STREAM_REDIS_PORT, {
                    ssl = true
                })
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end
                ngx.say("sock reusetimes: ", red:get_reused_times())

                ok, err = red:select(1)
                if not ok then
                    ngx.say("failed to select: ", err)
                    return
                end

                local res, err = red:set("dog", "an animal")
                if not res then
                    ngx.say("failed to set dog: ", err)
                    return
                end

                ngx.say("set dog: ", res)

                local ok, err = red:set_keepalive()
                if not ok then
                    ngx.say("failed to set keepalive: ", err)
                    return
                end
            end

            connect_set(red)
            connect_set(red)
        }
    }
--- response_body eval
qr/sock reusetimes: (0|2)
set dog: OK
sock reusetimes: (1|3)
set dog: OK/
