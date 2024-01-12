# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;
use Cwd qw(cwd);

#worker_connections(1014);
#master_process_enabled(1);
log_level('debug');

#repeat_each(120);
repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 13);

#no_diff();
#no_long_string();

my $pwd = cwd();

add_block_preprocessor(sub {
    my $block = shift;

    my $http_config = $block->http_config || '';

    $http_config .= <<_EOC_;

    lua_package_path "$pwd/lib/?.lua;\$prefix/html/?.lua;../lua-resty-lrucache/lib/?.lua;;";
    init_by_lua_block {
        local verbose = false
        if verbose then
            local dump = require "jit.dump"
            dump.on(nil, "$Test::Nginx::Util::ErrLogFile")
        else
            local v = require "jit.v"
            v.on("$Test::Nginx::Util::ErrLogFile")
        end

        require "resty.core"
        -- jit.off()
    }
_EOC_

    $block->set_value("http_config", $http_config);
});

check_accum_error_log();

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

run_tests();

__DATA__

=== TEST 1: get ngx.ctx
--- config
    location = /t {
        content_by_lua_block {
            for i = 1, 100 do
                ngx.ctx.foo = i
            end
            ngx.say("ctx.foo = ", ngx.ctx.foo)
        }
    }
--- request
GET /t
--- response_body
ctx.foo = 100
--- no_error_log
[error]
 -- NYI:
 bad argument
--- error_log eval
qr/\[TRACE\s+\d+\s+content_by_lua\(nginx\.conf:\d+\):2 loop\]/



=== TEST 2: set ngx.ctx
--- config
    location = /t {
        content_by_lua_block {
            for i = 1, 100 do
                ngx.ctx = {foo = i}
            end
            ngx.say("ctx.foo = ", ngx.ctx.foo)
        }
    }
--- request
GET /t
--- response_body
ctx.foo = 100
--- no_error_log
[error]
 -- NYI:
 bad argument
--- error_log eval
qr/\[TRACE\s+\d+\s+content_by_lua\(nginx\.conf:\d+\):2 loop\]/



=== TEST 3: ngx.ctx in ssl_certificate_by_lua
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            ngx.ctx.answer = 42
            ngx.log(ngx.WARN, "ngx.ctx.answer = ", ngx.ctx.answer)

            ngx.ctx.count = 0
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            content_by_lua_block {
                ngx.say(ngx.ctx.answer)
                ngx.ctx.count = ngx.ctx.count + 1
                ngx.say(ngx.ctx.count)
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
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
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.print("received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                sock:close()
            end  -- do
            -- collectgarbage()
        }
    }

--- request
GET /t
--- response_body
received: 42
received: 1
received: 42
received: 1
--- error_log
ngx.ctx.answer = 42
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 4: ngx.ctx in ssl_certificate_by_lua (share objects)
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            ngx.ctx.req = { count = 0 }
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            content_by_lua_block {
                ngx.ctx.req.count = ngx.ctx.req.count + 1
                ngx.say(ngx.ctx.req.count)
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
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
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.print("received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                sock:close()
            end  -- do
            -- collectgarbage()
        }
    }

--- request
GET /t
--- response_body
received: 1
received: 2
--- no_error_log
[error]



=== TEST 5: ngx.ctx in ssl_certificate_by_lua (release ctx when client aborted)
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            ssl.clear_certs()
            ngx.ctx.answer = 42
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            return 200 "ok";
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
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
    }

--- request
GET /t
--- response_body
failed to do SSL handshake: handshake failed
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 1
"]



=== TEST 6: ngx.ctx in ssl_session_store_by_lua
--- http_config
    ssl_session_store_by_lua_block {
        ngx.ctx.answer = 42
        ngx.log(ngx.WARN, "ngx.ctx.answer = ", ngx.ctx.answer)

        ngx.ctx.count = 0
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            content_by_lua_block {
                ngx.say(ngx.ctx.answer)
                ngx.ctx.count = ngx.ctx.count + 1
                ngx.say(ngx.ctx.count)
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()
                sock:settimeout(3000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(package.loaded.session, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.print("received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                package.loaded.session = sess
                sock:close()
            end  -- do
        }
    }
--- request
GET /t
--- response_body
received: 42
received: 1
received: 42
received: 1
--- error_log
ngx.ctx.answer = 42
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 7: ngx.ctx in ssl_session_store_by_lua (release ctx when client aborted)
--- http_config
    ssl_session_store_by_lua_block {
        ngx.ctx.answer = 42
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            return 200 "ok";
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()
                sock:settimeout(3000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(package.loaded.session, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("closed")
                sock:close()
            end  -- do
        }
    }
--- request
GET /t
--- response_body
closed
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 8: ngx.ctx in ssl_session_fetch_by_lua
--- http_config
    ssl_session_fetch_by_lua_block {
        ngx.ctx.answer = 42
        ngx.ctx.count = 0
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            content_by_lua_block {
                if package.loaded.session then
                    ngx.say(ngx.ctx.answer)
                    ngx.ctx.count = ngx.ctx.count + 1
                    ngx.say(ngx.ctx.count)
                end
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()
                sock:settimeout(3000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(package.loaded.session, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.log(ngx.WARN, "received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                package.loaded.session = sess
                sock:close()
            end  -- do
        }
    }
--- request
GET /t
--- grep_error_log eval
qr/(received: \w+|lua release ngx.ctx at ref \d+)/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
received: 42
received: 1
lua release ngx.ctx at ref 2
received: 42
received: 1
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 9: ngx.ctx in ssl_session_fetch_by_lua (release ctx when client aborted)
--- http_config
    ssl_session_fetch_by_lua_block {
        ngx.ctx.answer = 42
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            return 200 "ok";
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()
                sock:settimeout(3000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(package.loaded.session, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                package.loaded.session = sess
                ngx.say("closed")
                sock:close()
            end  -- do
        }
    }
--- request
GET /t
--- response_body
closed
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 10: ngx.ctx in ssl* and other phases
--- http_config
    ssl_session_store_by_lua_block {
        ngx.ctx.count = ngx.ctx.count and (ngx.ctx.count + 1) or 1
    }

    ssl_session_fetch_by_lua_block {
        ngx.ctx.count = ngx.ctx.count and (ngx.ctx.count + 10) or 10
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        ssl_certificate_by_lua_block {
            ngx.ctx.count = ngx.ctx.count and (ngx.ctx.count + 100) or 100
        }
        server_tokens off;
        location /foo {
            content_by_lua_block {
                ngx.ctx.count = ngx.ctx.count + 1
                ngx.say(ngx.ctx.count)
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()
                sock:settimeout(3000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                local sess, err = sock:sslhandshake(package.loaded.session, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.log(ngx.WARN, "received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                package.loaded.session = sess
                sock:close()
            end  -- do
        }
    }
--- request
GET /t
--- grep_error_log eval
qr/(received: \w+|lua release ngx.ctx at ref \d+)/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 2
received: 112
lua release ngx.ctx at ref 2
received: 112
lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 2
received: 112
lua release ngx.ctx at ref 2
received: 112
lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
received: 112
lua release ngx.ctx at ref 2
received: 112
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]



=== TEST 11: overwrite values will only take affect in the current http request
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            ngx.ctx.answer = 0
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo1 {
            content_by_lua_block {
                ngx.say(ngx.ctx.answer)
                ngx.ctx.answer = 42
            }
        }
        location /foo2 {
            content_by_lua_block {
                ngx.say(ngx.ctx.answer)
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
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
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo" .. i .. " HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.print("received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                sock:close()
            end  -- do
            -- collectgarbage()
        }
    }

--- request
GET /t
--- response_body
received: 0
received: 0



=== TEST 12: prohibit setting ngx.ctx to non-table value
--- config
    location = /t {
        content_by_lua_block {
            local ok, err = pcall(function()
                ngx.ctx = nil
            end)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- request
GET /t
--- response_body_like
ctx should be a table while getting a nil
--- no_error_log
[error]



=== TEST 13: get_ctx_table
--- config
    location = /t {
        content_by_lua_block {
            local get_ctx_table = require "resty.core.ctx" .get_ctx_table

            local reused_ctx = {}
            local ctx = get_ctx_table(reused_ctx)
            if ctx == reused_ctx then
                ngx.say("reused")
            end

            local ctx2 = get_ctx_table()
            if ctx2 == reused_ctx then
                ngx.say("reused again")
            end
        }
    }
--- request
GET /t
--- response_body
reused
reused again
--- no_error_log
[error]



=== TEST 14: ngx.ctx in ssl_client_hello_by_lua
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_client_hello_by_lua_block {
            ngx.ctx.answer = 42
            ngx.log(ngx.WARN, "ngx.ctx.answer = ", ngx.ctx.answer)

            ngx.ctx.count = 0
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            content_by_lua_block {
                ngx.say(ngx.ctx.answer)
                ngx.ctx.count = ngx.ctx.count + 1
                ngx.say(ngx.ctx.count)
            }
        }
    }
--- config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    location /t {
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
                    return
                end

                for i = 1, 2 do
                    local req = "GET /foo HTTP/1.1\r\nHost: test.com\r\n\r\n"
                    local bytes, err = sock:send(req)
                    if not bytes then
                        ngx.say("failed to send http request: ", err)
                        return
                    end

                    local body_seen = false
                    while true do
                        local line, err = sock:receive()
                        if not line then
                            break
                        end

                        if body_seen then
                            if line == "0" then
                                assert(sock:receive())
                                break
                            end
                            local line, err = sock:receive(line)
                            ngx.print("received: ", line)
                            assert(sock:receive())

                        elseif line == "" then
                            body_seen = true
                        end
                    end
                end

                sock:close()
            end  -- do
            -- collectgarbage()
        }
    }

--- request
GET /t
--- response_body
received: 42
received: 1
received: 42
received: 1
--- error_log
ngx.ctx.answer = 42
--- grep_error_log eval
qr/lua release ngx.ctx at ref \d+/
--- grep_error_log_out eval
["lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
",
"lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 2
lua release ngx.ctx at ref 1
"]
--- no_error_log
[error]
