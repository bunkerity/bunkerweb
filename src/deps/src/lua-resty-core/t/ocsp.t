# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(10140);
#workers(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 6 + 13);

no_long_string();
#no_diff();

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::lua_package_path";
$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

run_tests();

__DATA__

=== TEST 1: get OCSP responder (good case)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            -- specify the max length explicitly here, since string buf size may be too short
            local url, err = ocsp.get_ocsp_responder_from_der_chain(cert_data, 128)
            if not url then
                ngx.log(ngx.ERR, "failed to get OCSP responder: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP url found: ", url)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    location /t {
        content_by_lua_block {
            do
                local sock = ngx.socket.tcp()

                sock:settimeout(3000)

                local err
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
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP url found: http://127.0.0.1:8888/ocsp?foo=1,

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 2: get OCSP responder (not found)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/chain/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local url, err = ocsp.get_ocsp_responder_from_der_chain(cert_data)
            if not url then
                if err then
                    ngx.log(ngx.ERR, "failed to get OCSP responder: ", err)
                else
                    ngx.log(ngx.WARN, "OCSP responder not found")
                end
                return
            end

            ngx.log(ngx.WARN, "OCSP url found: ", url)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP responder not found

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 3: get OCSP responder (no issuer cert at all)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/test-com.crt"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local url, err = ocsp.get_ocsp_responder_from_der_chain(cert_data)
            if not url then
                if err then
                    ngx.log(ngx.ERR, "failed to get OCSP responder: ", err)
                else
                    ngx.log(ngx.WARN, "OCSP responder not found")
                end
                return
            end

            ngx.log(ngx.WARN, "OCSP url found: ", url)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
failed to get OCSP responder: no issuer certificate in chain

--- no_error_log
[alert]
[emerg]



=== TEST 4: get OCSP responder (issuer cert not next to the leaf cert)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/wrong-issuer-order-chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local url, err = ocsp.get_ocsp_responder_from_der_chain(cert_data)
            if not url then
                if err then
                    ngx.log(ngx.ERR, "failed to get OCSP responder: ", err)
                else
                    ngx.log(ngx.WARN, "OCSP responder not found")
                end
                return
            end

            ngx.log(ngx.WARN, "OCSP url found: ", url)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
failed to get OCSP responder: issuer certificate not next to leaf

--- no_error_log
[alert]
[emerg]



=== TEST 5: get OCSP responder (truncated)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local url, err = ocsp.get_ocsp_responder_from_der_chain(cert_data, 6)
            if not url then
                if err then
                    ngx.log(ngx.ERR, "failed to get OCSP responder: ", err)
                else
                    ngx.log(ngx.WARN, "OCSP responder not found")
                end
                return
            end

            if err then
                ngx.log(ngx.WARN, "still get an error: ", err)
            end

            ngx.log(ngx.WARN, "OCSP url found: ", url)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP url found: http:/,
still get an error: truncated

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 6: create OCSP request (good)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            -- specify the max length explicitly here, since string buf size may be too short
            local req, err = ocsp.create_ocsp_request(cert_data, 128)
            if not req then
                ngx.log(ngx.ERR, "failed to create OCSP request: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP request created with length ", #req)

            local f = assert(io.open("t/cert/ocsp/ocsp-req.der", "r"))
            local expected = assert(f:read("*a"))
            f:close()
            if req ~= expected then
                ngx.log(ngx.ERR, "ocsp responder: got unexpected OCSP request")
            end
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP request created with length 68

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 7: create OCSP request (buffer too small)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local req, err = ocsp.create_ocsp_request(cert_data, 67)
            if not req then
                ngx.log(ngx.ERR, "failed to create OCSP request: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP request created with length ", #req)
            local bytes = {string.byte(req, 1, #req)}
            for i, byte in ipairs(bytes) do
                bytes[i] = string.format("%02x", byte)
            end
            ngx.log(ngx.WARN, "OCSP request content: ", table.concat(bytes, " "))
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
failed to create OCSP request: output buffer too small: 68 > 67

--- no_error_log
[alert]
[emerg]



=== TEST 8: create OCSP request (empty string cert chain)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local cert_data = ""
            local req, err = ocsp.create_ocsp_request(cert_data, 67)
            if not req then
                ngx.log(ngx.ERR, "failed to create OCSP request: ", err)
                return ngx.exit(ngx.ERROR)
            end

            ngx.log(ngx.WARN, "OCSP request created with length ", #req)
            local bytes = {string.byte(req, 1, #req)}
            for i, byte in ipairs(bytes) do
                bytes[i] = string.format("%02x", byte)
            end
            ngx.log(ngx.WARN, "OCSP request content: ", table.concat(bytes, " "))
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
failed to do SSL handshake: handshake failed

--- error_log
lua ssl server name: "test.com"
failed to create OCSP request: d2i_X509_bio() failed

--- no_error_log
[alert]
[emerg]



=== TEST 9: create OCSP request (no issuer cert in the chain)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/test-com.crt"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local req, err = ocsp.create_ocsp_request(cert_data, 67)
            if not req then
                ngx.log(ngx.ERR, "failed to create OCSP request: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP request created with length ", #req)
            local bytes = {string.byte(req, 1, #req)}
            for i, byte in ipairs(bytes) do
                bytes[i] = string.format("%02x", byte)
            end
            ngx.log(ngx.WARN, "OCSP request content: ", table.concat(bytes, " "))
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
failed to create OCSP request: no issuer certificate in chain

--- no_error_log
[alert]
[emerg]



=== TEST 10: validate good OCSP response
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/ocsp/ocsp-resp.der"))
            local resp = f:read("*a")
            f:close()

            local ok, err = ocsp.validate_ocsp_response(resp, cert_data)
            if not ok then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP response validation ok")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP response validation ok

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 11: fail to validate OCSP response - no issuer cert
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/test-com.crt"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/ocsp/ocsp-resp.der"))
            local resp = f:read("*a")
            f:close()

            -- specify the max length explicitly here, since string buf size may be too short
            local req, err = ocsp.validate_ocsp_response(resp, cert_data, 128)
            if not req then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP response validation ok")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
failed to validate OCSP response: no issuer certificate in chain

--- no_error_log
OCSP response validation ok
[alert]
[emerg]



=== TEST 12: validate good OCSP response - no certs in response
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/ocsp/ocsp-resp-no-certs.der"))
            local resp = f:read("*a")
            f:close()

            local req, err = ocsp.validate_ocsp_response(resp, cert_data)
            if not req then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP response validation ok")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP response validation ok

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 13: validate OCSP response - OCSP response signed by an unknown cert and the OCSP response contains the unknown cert

FIXME: we should complain in this case.

--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/ocsp/ocsp-resp-signed-by-orphaned.der"))
            local resp = f:read("*a")
            f:close()

            local req, err = ocsp.validate_ocsp_response(resp, cert_data)
            if not req then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP response validation ok")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
OCSP response validation ok

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 14: fail to validate OCSP response - OCSP response signed by an unknown cert and the OCSP response does not contain the unknown cert

--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return
            end

            local f = assert(io.open("t/cert/ocsp/ocsp-resp-signed-by-orphaned-no-certs.der"))
            local resp = f:read("*a")
            f:close()

            -- specify the max length explicitly here, since string buf size may be too short
            local req, err = ocsp.validate_ocsp_response(resp, cert_data, 128)
            if not req then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return
            end

            ngx.log(ngx.WARN, "OCSP response validation ok")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
failed to validate OCSP response: OCSP_basic_verify() failed

--- no_error_log
OCSP response validation ok
[alert]
[emerg]



=== TEST 15: fail to validate OCSP response - OCSP response returns revoked status
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name   test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/revoked-chain.pem"))
            local cert_data = f:read("*a")
            f:close()

            local err
            cert_data, err = ssl.cert_pem_to_der(cert_data)
            if not cert_data then
                ngx.log(ngx.ERR, "failed to convert pem cert to der cert: ", err)
                return ngx.exit(ngx.ERROR)
            end

            local f = assert(io.open("t/cert/ocsp/revoked-ocsp-resp.der"))
            local resp = f:read("*a")
            f:close()

            -- specify the max length explicitly here, since string buf size may be too short
            local req, err = ocsp.validate_ocsp_response(resp, cert_data, 128)
            if not req then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return ngx.exit(ngx.ERROR)
            end

            ngx.log(ngx.WARN, "OCSP response validation ok")
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

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

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "test.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
failed to do SSL handshake: handshake failed

--- error_log
lua ssl server name: "test.com"
failed to validate OCSP response: certificate status "revoked" in the OCSP response

--- no_error_log
OCSP response validation ok
[alert]
[emerg]



=== TEST 16: good status req from client
FIXME: check the OCSP staple actually received by the ssl client
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        server_name test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/ocsp-resp.der"))
            local resp = assert(f:read("*a"))
            f:close()

            print("resp len: ", #resp)

            local ok, err = ocsp.set_ocsp_status_resp(resp)
            if not ok then
                ngx.log(ngx.ERR, "failed to set ocsp status resp: ", err)
                return
            end
            ngx.log(ngx.WARN, "ocsp status resp set ok: ", err)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    location /t {
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

                local sess, err = sock:sslhandshake(nil, "test.com", true, true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
ocsp status resp set ok: nil,

--- no_error_log
[error]
[alert]
[emerg]



=== TEST 17: no status req from client
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen 127.0.0.2:$TEST_NGINX_RAND_PORT_1 ssl;
        server_name test.com;
        ssl_certificate_by_lua_block {
            local ssl = require "ngx.ssl"
            local ocsp = require "ngx.ocsp"

            local f = assert(io.open("t/cert/ocsp/ocsp-resp.der"))
            local resp = assert(f:read("*a"))
            f:close()

            print("resp len: ", #resp)

            local ok, err = ocsp.set_ocsp_status_resp(resp)
            if not ok then
                ngx.log(ngx.ERR, "failed to set ocsp status resp: ", err)
                return
            end
            ngx.log(ngx.WARN, "ocsp status resp set ok: ", err)
        }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location /foo {
            default_type 'text/plain';
            content_by_lua_block {ngx.status = 201 ngx.say("foo") ngx.exit(201)}
            more_clear_headers Date;
        }
    }
--- config
    server_tokens off;
    lua_ssl_trusted_certificate ../../cert/test.crt;
    lua_ssl_verify_depth 3;

    location /t {
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

                local sess, err = sock:sslhandshake(nil, "test.com", true, false)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))
            end  -- do
        }
    }

--- request
GET /t
--- response_body
connected: 1
ssl handshake: cdata

--- error_log
lua ssl server name: "test.com"
ocsp status resp set ok: no status req,

--- no_error_log
[error]
[alert]
[emerg]
