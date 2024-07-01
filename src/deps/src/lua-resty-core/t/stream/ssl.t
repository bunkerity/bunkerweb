# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

#worker_connections(10140);
#workers(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 6 + 1);

no_long_string();
#no_diff();

env_to_nginx("PATH=" . $ENV{'PATH'});
$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::Stream::lua_package_path";
$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

run_tests();

__DATA__

=== TEST 1: clear certs
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            ssl.clear_certs()
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

            sock:settimeout(3000)

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
failed to do SSL handshake: handshake failed

--- error_log
lua ssl server name: "test.com"
sslv3 alert handshake failure

--- no_error_log
[alert]
[emerg]



=== TEST 2: set DER cert and private key
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/test.crt.der"))
            local cert_data = f:read("*a")
            f:close()

            local ok, err = ssl.set_der_cert(cert_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/test.key.der"))
            local pkey_data = f:read("*a")
            f:close()

            local ok, err = ssl.set_der_priv_key(pkey_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
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
[emerg]



=== TEST 3: read SNI name via ssl.server_name()
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            print("read SNI name from Lua: ", ssl.server_name())
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

            sock:settimeout(3000)

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
read SNI name from Lua: test.com

--- no_error_log
[error]
[alert]



=== TEST 4: read SNI name via ssl.server_name() when no SNI name specified
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local name = ssl.server_name(),
            print("read SNI name from Lua: ", name, ", type: ", type(name))
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

            sock:settimeout(3000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(nil, nil, true)
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
read SNI name from Lua: nil, type: nil

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 5: read raw server addr via ssl.raw_server_addr() (unix domain socket)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local addr, addrtyp, err = ssl.raw_server_addr()
            if not addr then
                ngx.log(ngx.ERR, "failed to fetch raw server addr: ", err)
                return
            end
            if addrtyp == "inet" then  -- IPv4
                ip = string.format("%d.%d.%d.%d", byte(addr, 1), byte(addr, 2),
                                   byte(addr, 3), byte(addr, 4))
                print("Using IPv4 address: ", ip)

            elseif addrtyp == "inet6" then  -- IPv6
                ip = string.format("%d.%d.%d.%d", byte(addr, 13), byte(addr, 14),
                                   byte(addr, 15), byte(addr, 16))
                print("Using IPv6 address: ", ip)

            else  -- unix
                print("Using unix socket file ", addr)
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

            sock:settimeout(3000)

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
qr/Using unix socket file .*?nginx\.sock/
]

--- no_error_log
[error]
[alert]
--- no_check_leak



=== TEST 6: read raw server addr via ssl.raw_server_addr() (IPv4)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.1:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local byte = string.byte

            local addr, addrtyp, err = ssl.raw_server_addr()
            if not addr then
                ngx.log(ngx.ERR, "failed to fetch raw server addr: ", err)
                return
            end
            if addrtyp == "inet" then  -- IPv4
                ip = string.format("%d.%d.%d.%d", byte(addr, 1), byte(addr, 2),
                                   byte(addr, 3), byte(addr, 4))
                print("Using IPv4 address: ", ip)

            elseif addrtyp == "inet6" then  -- IPv6
                ip = string.format("%d.%d.%d.%d", byte(addr, 13), byte(addr, 14),
                                   byte(addr, 15), byte(addr, 16))
                print("Using IPv6 address: ", ip)

            else  -- unix
                print("Using unix socket file ", addr)
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

            sock:settimeout(3000)

            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_RAND_PORT_1)
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
Using IPv4 address: 127.0.0.1

--- no_error_log
[error]
[alert]
--- no_check_leak



=== TEST 7: read raw server addr via ssl.raw_server_addr() (IPv6)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen [::1]:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local byte = string.byte

            local addr, addrtyp, err = ssl.raw_server_addr()
            if not addr then
                ngx.log(ngx.ERR, "failed to fetch raw server addr: ", err)
                return
            end
            if addrtyp == "inet" then  -- IPv4
                ip = string.format("%d.%d.%d.%d", byte(addr, 1), byte(addr, 2),
                                   byte(addr, 3), byte(addr, 4))
                print("Using IPv4 address: ", ip)

            elseif addrtyp == "inet6" then  -- IPv6
                ip = string.format("%d.%d.%d.%d", byte(addr, 13), byte(addr, 14),
                                   byte(addr, 15), byte(addr, 16))
                print("Using IPv6 address: ", ip)

            else  -- unix
                print("Using unix socket file ", addr)
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

            sock:settimeout(3000)

            local ok, err = sock:connect("[::1]", $TEST_NGINX_RAND_PORT_1)
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
Using IPv6 address: 0.0.0.1

--- no_error_log
[error]
[alert]
--- skip_eval: 6: system("ping6 -c 1 ::1 >/dev/null 2>&1") ne 0
--- no_check_leak



=== TEST 8: set DER cert chain
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain.der"))
            local cert_data = f:read("*a")
            f:close()

            local ok, err = ssl.set_der_cert(cert_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com.key.der"))
            local pkey_data = f:read("*a")
            f:close()

            local ok, err = ssl.set_der_priv_key(pkey_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
[emerg]



=== TEST 9: read PEM cert chain but set DER cert chain
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.cert_pem_to_der(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local ok, err = ssl.set_der_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com.key.der"))
            local pkey_data = f:read("*a")
            f:close()

            local ok, err = ssl.set_der_priv_key(pkey_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
[emerg]



=== TEST 10: tls version - SSLv3
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local ver, err = ssl.get_tls1_version_str(resp)
            if not ver then
                ngx.log(ngx.ERR, "failed to get TLS1 version: ", err)
                return
            end
            ngx.log(ngx.WARN, "got TLS1 version: ", ver)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        ssl_protocols SSLv3;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;
    lua_ssl_protocols SSLv3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
got TLS1 version: SSLv3,

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 11: tls version - TLSv1
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local ver, err = ssl.get_tls1_version_str(resp)
            if not ver then
                ngx.log(ngx.ERR, "failed to get TLS1 version: ", err)
                return
            end
            ngx.log(ngx.WARN, "got TLS1 version: ", ver)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        ssl_protocols TLSv1;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;
    lua_ssl_protocols TLSv1;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
got TLS1 version: TLSv1,

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 12: tls version - TLSv1.1
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local ver, err = ssl.get_tls1_version_str(resp)
            if not ver then
                ngx.log(ngx.ERR, "failed to get TLS1 version: ", err)
                return
            end
            ngx.log(ngx.WARN, "got TLS1 version: ", ver)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        ssl_protocols TLSv1.1;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;
    lua_ssl_protocols TLSv1.1;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
got TLS1 version: TLSv1.1,

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 13: tls version - TLSv1.2
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local ver, err = ssl.get_tls1_version_str(resp)
            if not ver then
                ngx.log(ngx.ERR, "failed to get TLS1 version: ", err)
                return
            end
            ngx.log(ngx.WARN, "got TLS1 version: ", ver)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        ssl_protocols TLSv1.2;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;
    lua_ssl_protocols TLSv1.2;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
got TLS1 version: TLSv1.2,

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 14: ngx.semaphore in ssl_certificate_by_lua*
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
            local semaphore = require "ngx.semaphore"

            local sema = assert(semaphore.new())

            local function f()
                assert(sema:wait(1))
            end

            local t = assert(ngx.thread.spawn(f))
            ngx.sleep(0.25)

            assert(sema:post())

            assert(ngx.thread.wait(t))
            print("ssl cert by lua done")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        ssl_protocols TLSv1.2;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;
    lua_ssl_protocols TLSv1.2;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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

--- grep_error_log eval: qr/stream lua semaphore (?:wait yielding|\w[^:,]*)/
--- grep_error_log_out
stream lua semaphore new
stream lua semaphore wait
stream lua semaphore wait yielding
stream lua semaphore post
--- error_log
ssl cert by lua done

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 15: read PEM key chain but set DER key chain
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.cert_pem_to_der(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local ok, err = ssl.set_der_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com.key.pem"))
            local pkey_data = f:read("*a")
            f:close()

            pkey_data, err = ssl.priv_key_pem_to_der(pkey_data)
            if not pkey_data then
                ngx.log(ngx.ERR, "failed to convert pem key to der key: ", err)
                return
            end
            local ok, err = ssl.set_der_priv_key(pkey_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
[emerg]



=== TEST 16: parse PEM cert and key to cdata
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.parse_pem_cert(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to parse pem cert: ", err)
                return
            end

            local ok, err = ssl.set_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com.key.pem"))
            local pkey_data = f:read("*a")
            f:close()

            local pkey, err = ssl.parse_pem_priv_key(pkey_data)
            if not pkey then
                ngx.log(ngx.ERR, "failed to parse pem key: ", err)
                return
            end

            local ok, err = ssl.set_priv_key(pkey)
            if not ok then
                ngx.log(ngx.ERR, "failed to set private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
[emerg]



=== TEST 17: parse PEM cert and key to cdata (bad cert 0 in the chain)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain-bad0.pem"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.parse_pem_cert(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to parse pem cert: ", err)
                return
            end

            local ok, err = ssl.set_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com.key.pem"))
            local pkey_data = f:read("*a")
            f:close()

            local pkey, err = ssl.parse_pem_priv_key(pkey_data)
            if not pkey then
                ngx.log(ngx.ERR, "failed to parse pem key: ", err)
                return
            end

            local ok, err = ssl.set_priv_key(pkey)
            if not ok then
                ngx.log(ngx.ERR, "failed to set private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
failed to do SSL handshake: handshake failed

--- error_log eval
qr/\[error\] .*? failed to parse pem cert: PEM_read_bio_X509_AUX\(\) failed/

--- no_error_log
[alert]
[emerg]
[crit]



=== TEST 18: parse PEM cert and key to cdata (bad cert 2 in the chain)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain-bad2.pem"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.parse_pem_cert(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to parse pem cert: ", err)
                return
            end

            local ok, err = ssl.set_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com.key.pem"))
            local pkey_data = f:read("*a")
            f:close()

            local pkey, err = ssl.parse_pem_priv_key(pkey_data)
            if not pkey then
                ngx.log(ngx.ERR, "failed to parse pem key: ", err)
                return
            end

            local ok, err = ssl.set_priv_key(pkey)
            if not ok then
                ngx.log(ngx.ERR, "failed to set private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
failed to do SSL handshake: handshake failed

--- error_log eval
qr/\[error\] .*? failed to parse pem cert: PEM_read_bio_X509\(\) failed/

--- no_error_log
[alert]
[emerg]
[crit]



=== TEST 19: parse PEM cert and key to cdata (bad priv key)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/chain/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.parse_pem_cert(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to parse pem cert: ", err)
                return
            end

            local ok, err = ssl.set_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/chain/test-com-bad.key.pem"))
            local pkey_data = f:read("*a")
            f:close()

            local pkey, err = ssl.parse_pem_priv_key(pkey_data)
            if not pkey then
                ngx.log(ngx.ERR, "failed to parse pem key: ", err)
                return
            end

            local ok, err = ssl.set_priv_key(pkey)
            if not ok then
                ngx.log(ngx.ERR, "failed to set private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

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
failed to do SSL handshake: handshake failed

--- error_log eval
qr/\[error\] .*? failed to parse pem key: PEM_read_bio_PrivateKey\(\) failed/

--- no_error_log
[alert]
[emerg]
[crit]



=== TEST 20: read client addr via ssl.raw_client_addr()
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.1:$TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate_by_lua_block {
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

            sock:settimeout(3000)

            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_RAND_PORT_1)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(nil, nil, true)
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
[emerg]



=== TEST 21: yield during doing handshake with client which uses low version OpenSSL
--- no_check_leak
--- stream_config
    lua_shared_dict done 16k;
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH/?.lua;;";
    server {
        listen $TEST_NGINX_RAND_PORT_1 ssl;
        ssl_session_tickets off;
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/test.crt.der"))
            local cert_data = f:read("*a")
            f:close()

            ngx.sleep(0.01) -- yield

            local ok, err = ssl.set_der_cert(cert_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/test.key.der"))
            local pkey_data = f:read("*a")
            f:close()

            local ok, err = ssl.set_der_priv_key(pkey_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end
        }

        content_by_lua_block {
            ngx.shared.done:set("handshake", true)
        }
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        ngx.shared.done:delete("handshake")
        local addr = ngx.var.addr;
        local req = "'GET / HTTP/1.0\r\nHost: test.com\r\nConnection: close\r\n\r\n'"
        local f, err = io.popen("echo -n " .. req .. " | timeout 3s openssl s_client -connect 127.0.0.1:$TEST_NGINX_RAND_PORT_1")
        if not f then
            ngx.say(err)
            return
        end

        local step = 0.001
        while step < 2 do
            ngx.sleep(step)
            step = step * 2

            if ngx.shared.done:get("handshake") then
                local out = f:read('*a')
                ngx.log(ngx.INFO, out)
                ngx.say("ok")
                f:close()
                return
            end
        end

        ngx.log(ngx.ERR, "openssl client handshake timeout")
    }

--- stream_response
ok
--- error_log eval
[
qr/content_by_lua\(nginx\.conf:\d+\):\d+: CONNECTED/,
qr/subject=\/?C(?<eq>\s?=\s?)US(?<sep>\/|,\s)ST\k<eq>California\k<sep>L\k<eq>San Francisco\k<sep>O\k<eq>OpenResty\k<sep>OU\k<eq>OpenResty\k<sep>CN\k<eq>test\.com\k<sep>emailAddress\k<eq>agentzh\@gmail\.com/,
]

--- no_error_log
[error]
[alert]
--- timeout: 5



=== TEST 22: tls version - TLSv1.3
--- skip_openssl: 6: < 1.1.1
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        ssl_protocols TLSv1.3;

        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local ver, err = ssl.get_tls1_version_str(resp)
            if not ver then
                ngx.log(ngx.ERR, "failed to get TLS1 version: ", err)
                return
            end
            ngx.log(ngx.WARN, "got TLS1 version: ", ver)
        }

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;
    lua_ssl_protocols TLSv1.3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
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
got TLS1 version: TLSv1.3,
--- no_error_log
[error]
[alert]
[emerg]



=== TEST 23: verify client with CA certificates
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;

        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local f = assert(io.open("t/cert/test.crt", "rb"))
            local cert_data = f:read("*all")
            f:close()

            local cert = ssl.parse_pem_cert(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to parse pem cert: ", err)
                return
            end

            local ok, err = ssl.verify_client(cert, 1)
            if not ok then
                ngx.log(ngx.ERR, "failed to verify client: ", err)
                return
            end
        }

        content_by_lua_block {
            print('client certificate subject: ', ngx.var.ssl_client_s_dn)
            ngx.say(ngx.var.ssl_client_verify)
        }
    }
--- stream_server_config
    proxy_pass                  unix:$TEST_NGINX_HTML_DIR/nginx.sock;
    proxy_ssl                   on;
    proxy_ssl_certificate       ../../cert/test.crt;
    proxy_ssl_certificate_key   ../../cert/test.key;
    proxy_ssl_session_reuse     off;

--- stream_response
SUCCESS

--- error_log
client certificate subject: emailAddress=agentzh@gmail.com,CN=test.com

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 24: verify client without CA certificates
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;

        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local ok, err = ssl.verify_client()
            if not ok then
                ngx.log(ngx.ERR, "failed to verify client: ", err)
                return
            end
        }

        content_by_lua_block {
            print('client certificate subject: ', ngx.var.ssl_client_s_dn)
            ngx.say(ngx.var.ssl_client_verify)
        }
    }
--- stream_server_config
    proxy_pass                  unix:$TEST_NGINX_HTML_DIR/nginx.sock;
    proxy_ssl                   on;
    proxy_ssl_certificate       ../../cert/test.crt;
    proxy_ssl_certificate_key   ../../cert/test.key;
    proxy_ssl_session_reuse     off;

--- stream_response
FAILED:self signed certificate

--- error_log
client certificate subject: emailAddress=agentzh@gmail.com,CN=test.com

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 25: verify client but client provides no certificate
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;

        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            local f = assert(io.open("t/cert/test.crt", "rb"))
            local cert_data = f:read("*all")
            f:close()

            local cert = ssl.parse_pem_cert(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to parse pem cert: ", err)
                return
            end

            local ok, err = ssl.verify_client(cert, 1)
            if not ok then
                ngx.log(ngx.ERR, "failed to verify client: ", err)
                return
            end
        }

        content_by_lua_block {
            print('client certificate subject: ', ngx.var.ssl_client_s_dn)
            ngx.say(ngx.var.ssl_client_verify)
        }
    }
--- stream_server_config
    proxy_pass                  unix:$TEST_NGINX_HTML_DIR/nginx.sock;
    proxy_ssl                   on;
    proxy_ssl_session_reuse     off;

--- stream_response
NONE

--- error_log
client certificate subject: nil

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 26: private key protected by passphrase
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"

            ssl.clear_certs()

            local f = assert(io.open("t/cert/test_passphrase.crt"))
            local cert_data = f:read("*a")
            f:close()

            local cert, err = ssl.cert_pem_to_der(cert_data)
            if not cert then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local ok, err = ssl.set_der_cert(cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/test_passphrase.key"))
            local pkey_data = f:read("*a")
            f:close()

            pkey_data, err = ssl.priv_key_pem_to_der(pkey_data, "123456")
            if not pkey_data then
                ngx.log(ngx.ERR, "failed to convert pem key to der key: ", err)
                return
            end

            local ok, err = ssl.set_der_priv_key(pkey_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to set DER private key: ", err)
                return
            end
        }
        ssl_certificate ../../cert/test2.crt;
        ssl_certificate_key ../../cert/test2.key;

        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_trusted_certificate ../../cert/chain/root-ca.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(3000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(nil, "test.com")
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
[emerg]
