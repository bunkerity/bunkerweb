# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;
use Cwd qw(abs_path realpath);
use File::Basename;

#worker_connections(10140);
#workers(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 6 + 2);

no_long_string();
#no_diff();

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::lua_package_path";
$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';
$ENV{TEST_NGINX_CERT_DIR} ||= dirname(realpath(abs_path(__FILE__)));

run_tests();

__DATA__

=== TEST 1: get new session serialized
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    ssl_session_store_by_lua_block {
        local ssl = require "ngx.ssl.session"
        local sess = ssl.get_serialized_session()
        print("session size: ", #sess)
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        server_tokens off;
    }
--- config
    server_tokens off;
    resolver $TEST_NGINX_RESOLVER;
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
    lua_ssl_verify_depth 3;

    location /t {
        set $port $TEST_NGINX_MEMCACHED_PORT;

        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()

                sock:settimeout(5000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))

                local ok, err = sock:close()
                ngx.say("close: ", ok, " ", err)
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata
close: 1 nil

--- error_log eval
qr/ssl_session_store_by_lua\(nginx.conf:\d+\):4: session size: \d+/s

--- no_error_log
[alert]
[emerg]
[error]



=== TEST 2: get new session id serialized
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    ssl_session_store_by_lua_block {
        local ssl = require "ngx.ssl.session"
        local sid = ssl.get_session_id()
        print("session id: ", sid)
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        server_tokens off;
    }
--- config
    server_tokens off;
    resolver $TEST_NGINX_RESOLVER;
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
    lua_ssl_verify_depth 3;

    location /t {
        set $port $TEST_NGINX_MEMCACHED_PORT;

        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()

                sock:settimeout(5000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))

                local ok, err = sock:close()
                ngx.say("close: ", ok, " ", err)
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata
close: 1 nil

--- error_log eval
qr/ssl_session_store_by_lua\(nginx.conf:\d+\):4: session id: [a-fA-f\d]+/s

--- no_error_log
[alert]
[emerg]
[error]



=== TEST 3: store the session via timer to memcached
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    ssl_session_store_by_lua_block {
        local ssl = require "ngx.ssl.session"
        local function f(premature, key, value)
           local sock = ngx.socket.tcp()

           sock:settimeout(5000)

           local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
           if not ok then
               ngx.log(ngx.ERR, "failed to connect to memc: ", err)
               return
           end

           local bytes, err = sock:send("set " .. key .. " 0 0 "
                                         .. tostring(#value) .. " \r\n"
                                         .. value .. "\r\n")
           if not bytes then
               ngx.log(ngx.ERR, "failed to send set command: ", err)
               return
           end

           local res, err = sock:receive()
           if not res then
               ngx.log(ngx.ERR, "failed to receive memc reply: ", err)
               return
           end

           print("received memc reply: ", res)
        end

        local sid = ssl.get_session_id()
        print("session id: ", sid)
        local sess = ssl.get_serialized_session()
        print("session size: ", #sess)

        local ok, err = ngx.timer.at(0, f, sid, sess)
        if not ok then
            ngx.log(ngx.ERR, "failed to create timer: ", err)
            return
        end
    }

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name test.com;
        ssl_session_tickets off;
        ssl_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        server_tokens off;
    }
--- config
    server_tokens off;
    resolver $TEST_NGINX_RESOLVER;
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
    lua_ssl_verify_depth 3;

    location /t {
        set $port $TEST_NGINX_MEMCACHED_PORT;

        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()

                sock:settimeout(5000)

                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))

                local ok, err = sock:close()
                ngx.say("close: ", ok, " ", err)
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata
close: 1 nil

--- error_log eval
[
qr/ssl_session_store_by_lua\(nginx.conf:\d+\):32: session id: [a-fA-f\d]+/s,
qr/ssl_session_store_by_lua\(nginx.conf:\d+\):34: session size: \d+/s,
qr/received memc reply: STORED/s,
]

--- no_error_log
[alert]
[emerg]
[error]
--- wait: 0.2
