# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
repeat_each(3);

# All these tests need to have new openssl
my $NginxBinary = $ENV{'TEST_NGINX_BINARY'} || 'nginx';
my $openssl_version = eval { `$NginxBinary -V 2>&1` };

if ($openssl_version =~ m/built with OpenSSL (0\S*|1\.0\S*|1\.1\.0\S*)/) {
    plan(skip_all => "too old OpenSSL, need 1.1.1, was $1");
} else {
    plan tests => repeat_each() * (blocks() * 6 + 5);
}

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();
$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;

#log_level 'warn';
log_level 'debug';

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: simple logging
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"

--- no_error_log
[error]
[alert]
--- grep_error_log eval: qr/ssl_client_hello_by_lua:.*?,|\bssl client hello: connection reusable: \d+|\breusable connection: \d+/
--- grep_error_log_out eval
qr/reusable connection: 1
reusable connection: 0
ssl client hello: connection reusable: 0
reusable connection: 0
ssl_client_hello_by_lua:1: ssl client hello by lua is running!,
reusable connection: 0
reusable connection: 0
reusable connection: 0
reusable connection: 0
reusable connection: 0
/



=== TEST 2: sleep
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            local begin = ngx.now()
            ngx.sleep(0.1)
            print("elapsed in ssl client hello by lua: ", ngx.now() - begin)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log eval
[
'lua ssl server name: "test.com"',
qr/elapsed in ssl client hello by lua: 0.(?:09|1\d)\d+,/,
]

--- no_error_log
[error]
[alert]



=== TEST 3: timer
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            local function f()
                print("my timer run!")
            end
            local ok, err = ngx.timer.at(0, f)
            if not ok then
                ngx.log(ngx.ERR, "failed to create timer: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"
my timer run!

--- no_error_log
[error]
[alert]



=== TEST 4: cosocket
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect to memc: ", err)
                return
            end

            local bytes, err = sock:send("flush_all\r\n")
            if not bytes then
                ngx.log(ngx.ERR, "failed to send flush_all command: ", err)
                return
            end

            local res, err = sock:receive()
            if not res then
                ngx.log(ngx.ERR, "failed to receive memc reply: ", err)
                return
            end

            print("received memc reply: ", res)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"
received memc reply: OK

--- no_error_log
[error]
[alert]



=== TEST 5: ngx.exit(0) - no yield
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_client_hello_by_lua_block {
            ngx.exit(0)
            ngx.log(ngx.ERR, "should never reached here...")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, nil, true, false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
    }

--- stream_response
connected: 1
ssl handshake: boolean

--- error_log
lua exit with code 0

--- no_error_log
should never reached here
[error]
[alert]
[emerg]



=== TEST 6: ngx.exit(ngx.ERROR) - no yield
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_client_hello_by_lua_block {
            ngx.exit(ngx.ERROR)
            ngx.log(ngx.ERR, "should never reached here...")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, nil, true, false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
    }

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed

--- error_log eval
[
'lua_client_hello_by_lua: handler return value: -1, client hello cb exit code: 0',
qr/\[info\] .*? SSL_do_handshake\(\) failed .*?callback failed/,
'lua exit with code -1',
]

--- no_error_log
should never reached here
[alert]
[emerg]



=== TEST 7: ngx.exit(0) -  yield
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_client_hello_by_lua_block {
            ngx.sleep(0.001)
            ngx.exit(0)

            ngx.log(ngx.ERR, "should never reached here...")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, nil, true, false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
    }

--- stream_response
connected: 1
ssl handshake: boolean

--- error_log
lua exit with code 0

--- no_error_log
should never reached here
[error]
[alert]
[emerg]



=== TEST 8: ngx.exit(ngx.ERROR) - yield
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_client_hello_by_lua_block {
            ngx.sleep(0.001)
            ngx.exit(ngx.ERROR)

            ngx.log(ngx.ERR, "should never reached here...")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, nil, true, false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
    }

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed

--- error_log eval
[
'lua_client_hello_by_lua: client hello cb exit code: 0',
qr/\[info\] .*? SSL_do_handshake\(\) failed .*?callback failed/,
'lua exit with code -1',
]

--- no_error_log
should never reached here
[alert]
[emerg]



=== TEST 9: lua exception - no yield
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_client_hello_by_lua_block {
            error("bad bad bad")
            ngx.log(ngx.ERR, "should never reached here...")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, nil, true, false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
    }

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed

--- error_log eval
[
'runtime error: ssl_client_hello_by_lua:2: bad bad bad',
'lua_client_hello_by_lua: handler return value: 500, client hello cb exit code: 0',
qr/\[info\] .*? SSL_do_handshake\(\) failed .*?callback failed/,
qr/context: ssl_client_hello_by_lua\*, client: \d+\.\d+\.\d+\.\d+, server: \d+\.\d+\.\d+\.\d+:\d+/,
]

--- no_error_log
should never reached here
[alert]
[emerg]



=== TEST 10: lua exception - yield
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_client_hello_by_lua_block {
            ngx.sleep(0.001)
            error("bad bad bad")
            ngx.log(ngx.ERR, "should never reached here...")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, nil, true, false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
    }

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed

--- error_log eval
[
'runtime error: ssl_client_hello_by_lua:3: bad bad bad',
'lua_client_hello_by_lua: client hello cb exit code: 0',
qr/\[info\] .*? SSL_do_handshake\(\) failed .*?callback failed/,
]

--- no_error_log
should never reached here
[alert]
[emerg]



=== TEST 11: get phase
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {print("get_phase: ", ngx.get_phase())}
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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
        end
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata

--- error_log
lua ssl server name: "test.com"
get_phase: ssl_client_hello

--- no_error_log
[error]
[alert]



=== TEST 12: connection aborted prematurely
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            ngx.sleep(0.3)
            -- local ssl = require "ngx.ssl"
            -- ssl.clear_certs()
            print("ssl-client-hello-by-lua: after sleeping")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(150)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false, "test.com", true)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
failed to do SSL handshake: timeout

--- error_log
lua ssl server name: "test.com"
ssl-client-hello-by-lua: after sleeping

--- no_error_log
[error]
[alert]
--- wait: 0.6



=== TEST 13: simple logging (by_lua_file)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_file html/a.lua;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }

--- user_files
>>> a.lua
print("ssl client hello by lua is running!")

--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"
a.lua:1: ssl client hello by lua is running!

--- no_error_log
[error]
[alert]



=== TEST 14: coroutine API
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            local cc, cr, cy = coroutine.create, coroutine.resume, coroutine.yield

            local function f()
                local cnt = 0
                for i = 1, 20 do
                    print("co yield: ", cnt)
                    cy()
                    cnt = cnt + 1
                end
            end

            local c = cc(f)
            for i = 1, 3 do
                print("co resume, status: ", coroutine.status(c))
                cr(c)
            end
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- grep_error_log eval: qr/co (?:yield: \d+|resume, status: \w+)/
--- grep_error_log_out
co resume, status: suspended
co yield: 0
co resume, status: suspended
co yield: 1
co resume, status: suspended
co yield: 2

--- error_log
lua ssl server name: "test.com"

--- no_error_log
[error]
[alert]



=== TEST 15: simple user thread wait with yielding
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            function f()
                ngx.sleep(0.01)
                print("uthread: hello in thread")
                return "done"
            end

            local t, err = ngx.thread.spawn(f)
            if not t then
                ngx.log(ngx.ERR, "uthread: failed to spawn thread: ", err)
                return ngx.exit(ngx.ERROR)
            end

            print("uthread: thread created: ", coroutine.status(t))

            local ok, res = ngx.thread.wait(t)
            if not ok then
                print("uthread: failed to wait thread: ", res)
                return
            end

            print("uthread: ", res)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- no_error_log
[error]
[alert]
--- grep_error_log eval: qr/uthread: [^.,]+/
--- grep_error_log_out
uthread: thread created: running
uthread: hello in thread
uthread: done



=== TEST 16: simple logging - use ssl_client_hello_by_lua* on the stream {} level
--- stream_config
    ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
    ssl_certificate ../../cert/test.crt;
    ssl_certificate_key ../../cert/test.key;

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"
ssl_client_hello_by_lua:1: ssl client hello by lua is running!

--- no_error_log
[error]
[alert]



=== TEST 17: simple logging - use ssl_client_hello_by_lua* on the stream {} level and server {} level
--- stream_config
    ssl_client_hello_by_lua_block { print("ssl client hello by lua on the stream level is running!") }
    ssl_certificate ../../cert/test.crt;
    ssl_certificate_key ../../cert/test.key;

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block { print("ssl client hello by lua on the server level is running!") }
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"
ssl_client_hello_by_lua:1: ssl client hello by lua on the server level is running!

--- no_error_log
[error]
[alert]



=== TEST 18: use ssl_client_hello_by_lua* on the server {} level with non-ssl server
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;
        ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
received: it works!
close: 1 nil

--- no_error_log
ssl_client_hello_by_lua:1: ssl client hello by lua is running!
[error]
[alert]



=== TEST 19: use ssl_client_hello_by_lua* on the stream {} level with non-ssl server
--- stream_config
    ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
received: it works!
close: 1 nil

--- no_error_log
ssl_client_hello_by_lua:1: ssl client hello by lua is running!
[error]
[alert]



=== TEST 20: listen two ports (one for ssl and one for non-ssl) in one server - connect ssl port
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_2;
        ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_1)
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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
lua ssl server name: "test.com"
ssl_client_hello_by_lua:1: ssl client hello by lua is running!

--- no_error_log
[error]
[alert]



=== TEST 21: listen two ports (one for ssl and one for non-ssl) in one server - connect non-ssl port
--- stream_config
    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_2;
        ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.2", $TEST_NGINX_RAND_PORT_2)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
received: it works!
close: 1 nil

--- no_error_log
ssl_client_hello_by_lua:1: ssl client hello by lua is running!
[error]
[alert]



=== TEST 22: simple logging (syslog)
github issue #723
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;

        error_log syslog:server=127.0.0.1:12345 debug;

        ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log eval
[
qr/\[error\] .*? send\(\) failed/,
'lua ssl server name: "test.com"',
]
--- no_error_log
[alert]
ssl_client_hello_by_lua:1: ssl client hello by lua is running!



=== TEST 23: get raw_client_addr - IPv4
--- stream_config
    lua_package_path "../lua-resty-core/lib/?.lua;;";

    server {
        listen 127.0.0.1:12346 ssl;

        ssl_client_hello_by_lua_block {
            local ssl = require "ngx.ssl"
            local byte = string.byte
            local addr, addrtype, err = ssl.raw_client_addr()
            local ip = string.format("%d.%d.%d.%d", byte(addr, 1), byte(addr, 2),
                       byte(addr, 3), byte(addr, 4))
            print("client ip: ", ip)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("127.0.0.1", 12346)
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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
client ip: 127.0.0.1

--- no_error_log
[error]
[alert]



=== TEST 24: get raw_client_addr - unix domain socket
--- stream_config
    lua_package_path "../lua-resty-core/lib/?.lua;;";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;

        ssl_client_hello_by_lua_block {
            local ssl = require "ngx.ssl"
            local addr, addrtyp, err = ssl.raw_client_addr()
            print("client socket file: ", addr)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to receive response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
received: it works!
close: 1 nil

--- error_log
client socket file: 

--- no_error_log
[error]
[alert]



=== TEST 25: cosocket (UDP)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            local sock = ngx.socket.udp()

            sock:settimeout(2000)

            local ok, err = sock:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect to memc: ", err)
                return
            end

            local req = "\0\1\0\0\0\1\0\0flush_all\r\n"
            local ok, err = sock:send(req)
            if not ok then
                ngx.log(ngx.ERR, "failed to send flush_all to memc: ", err)
                return
            end

            local res, err = sock:receive()
            if not res then
                ngx.log(ngx.ERR, "failed to receive memc reply: ", err)
                return
            end

            ngx.log(ngx.INFO, "received memc reply of ", #res, " bytes")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
--- no_error_log
[error]
[alert]
[emerg]
--- grep_error_log eval: qr/received memc reply of \d+ bytes/
--- grep_error_log_out eval
[
'received memc reply of 12 bytes
',
'received memc reply of 12 bytes
',
'received memc reply of 12 bytes
',
'received memc reply of 12 bytes
',
]



=== TEST 26: uthread (kill)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_client_hello_by_lua_block {
            local function f()
                ngx.log(ngx.INFO, "uthread: hello from f()")
                ngx.sleep(1)
            end

            local t, err = ngx.thread.spawn(f)
            if not t then
                ngx.log(ngx.ERR, "failed to spawn thread: ", err)
                return ngx.exit(ngx.ERROR)
            end

            local ok, res = ngx.thread.kill(t)
            if not ok then
                ngx.log(ngx.ERR, "failed to kill thread: ", res)
                return
            end

            ngx.log(ngx.INFO, "uthread: killed")

            local ok, err = ngx.thread.kill(t)
            if not ok then
                ngx.log(ngx.INFO, "uthread: failed to kill: ", err)
            end
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

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

        end  -- do
        -- collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
--- no_error_log
[error]
[alert]
[emerg]
--- grep_error_log eval: qr/uthread: [^.,]+/
--- grep_error_log_out
uthread: hello from f()
uthread: killed
uthread: failed to kill: already waited or killed
