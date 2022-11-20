# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 4);

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.ctx in ssl_certificate_by_lua
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            ngx.ctx.answer = 42
            ngx.log(ngx.WARN, "ngx.ctx.answer = ", ngx.ctx.answer)

            ngx.ctx.count = 0
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        content_by_lua_block {
            ngx.say(ngx.ctx.answer)
            ngx.ctx.count = ngx.ctx.count + 1
            ngx.say(ngx.ctx.count)
        }
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

            local function run()
                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                while true do
                    local line, err = sock:receive()
                    if not line then
                        break
                    end

                    ngx.say("received: ", line)
                end

                sock:close()
            end

            run()
        end  -- do
        -- collectgarbage()
    }

--- stream_response
received: 42
received: 1
--- error_log
ngx.ctx.answer = 42
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 2: ngx.ctx in ssl_certificate_by_lua (share objects)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            ngx.ctx.req = { count = 0 }
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        content_by_lua_block {
            ngx.ctx.req.count = ngx.ctx.req.count + 1
            ngx.say(ngx.ctx.req.count)
        }
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

            local function run()
                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                while true do
                    local line, err = sock:receive()
                    if not line then
                        break
                    end

                    ngx.say("received: ", line)
                end

                sock:close()
            end

            run()
        end  -- do
        -- collectgarbage()
    }

--- stream_response
received: 1
--- no_error_log
[error]



=== TEST 3: ngx.ctx in ssl_certificate_by_lua (release ctx when client aborted)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            ssl.clear_certs()
            ngx.ctx.answer = 42
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return "ok";
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()
            sock:settimeout(3000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local sess, err = sock:sslhandshake(nil, "test.com", true)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
            end

            sock:close()
        end  -- do
        -- collectgarbage()
    }

--- stream_response
failed to do SSL handshake: handshake failed
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 1
"]



=== TEST 4: ngx.ctx in ssl_client_hello_by_lua
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            ngx.ctx.answer = 42
            ngx.log(ngx.WARN, "ngx.ctx.answer = ", ngx.ctx.answer)

            ngx.ctx.count = 0
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        content_by_lua_block {
            ngx.say(ngx.ctx.answer)
            ngx.ctx.count = ngx.ctx.count + 1
            ngx.say(ngx.ctx.count)
        }
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

            local function run()
                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                while true do
                    local line, err = sock:receive()
                    if not line then
                        break
                    end

                    ngx.say("received: ", line)
                end

                sock:close()
            end

            run()
        end  -- do
        -- collectgarbage()
    }

--- stream_response
received: 42
received: 1
--- error_log
ngx.ctx.answer = 42
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]
