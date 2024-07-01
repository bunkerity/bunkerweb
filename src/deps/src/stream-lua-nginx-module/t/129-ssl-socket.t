# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
use Cwd qw(abs_path realpath);
use File::Basename;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 7 + 2);

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();
$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';
$ENV{TEST_NGINX_SERVER_SSL_PORT} ||= 12345;
$ENV{TEST_NGINX_CERT_DIR} ||= dirname(realpath(abs_path(__FILE__)));

#log_level 'warn';
log_level 'debug';

no_long_string();
#no_diff();

sub read_file {
    my $infile = shift;
    open my $in, $infile
        or die "cannot open $infile for reading: $!";
    my $cert = do { local $/; <$in> };
    close $in;
    $cert;
}

our $DSTRootCertificate = read_file("t/cert/root-ca.crt");
our $GoogleRootCertificate = read_file("t/cert/google.crt");
our $TestCertificate = read_file("t/cert/test.crt");
our $TestCertificateKey = read_file("t/cert/test.key");
our $TestCRL = read_file("t/cert/test.crl");

run_tests();

__DATA__

=== TEST 1: www.google.com
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua '
            -- avoid flushing google in "check leak" testing mode:
            local counter = package.loaded.counter
            if not counter then
                counter = 1
            elseif counter >= 2 then
                return ngx.exit(503)
            else
                counter = counter + 1
            end
            package.loaded.counter = counter

            do
                local sock = ngx.socket.tcp()
                sock:settimeout(2000)
                local ok, err = sock:connect("www.google.com", 443)
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake()
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))

                local req = "GET / HTTP/1.1\\r\\nHost: www.google.com\\r\\nConnection: close\\r\\n\\r\\n"
                local bytes, err = sock:send(req)
                if not bytes then
                    ngx.say("failed to send http request: ", err)
                    return
                end

                ngx.say("sent http request: ", bytes, " bytes.")

                local line, err = sock:receive()
                if not line then
                    ngx.say("failed to receive response status line: ", err)
                    return
                end

                ngx.say("received: ", line)

                local ok, err = sock:close()
                ngx.say("close: ", ok, " ", err)
            end  -- do
            collectgarbage()
        ';
--- config
    server_tokens off;
--- stream_response_like chop
\Aconnected: 1
ssl handshake: userdata
sent http request: 59 bytes.
received: HTTP/1.1 (?:200 OK|302 Found)
close: 1 nil
\z
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- no_error_log
lua ssl server name:
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 2: no SNI, no verify
--- stream_config
    server {
        listen $TEST_NGINX_SERVER_SSL_PORT ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "ping" then
                ngx.say("pong")
            end
        }
    }

--- stream_server_config
    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()
            sock:settimeout(2000)
            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake()
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "ping"
            local bytes, err = sock:send(req .. '\n')
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end

            ngx.say("sent: ", req)

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive response: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent: ping
received: pong
close: 1 nil

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- no_error_log
lua ssl server name:
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 3: SNI, no verify
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 4: ssl session reuse
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do

        local session
        for i = 1, 2 do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            session, err = sock:sslhandshake(session, "openresty.org")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end

        end -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil
connected: 1
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl set session: \1
lua ssl save session: \1
lua ssl free session: \1
lua ssl free session: \1
$/

--- error_log
SSL reused session
lua ssl free session

--- log_level: debug
--- no_error_log
[error]
[alert]
--- timeout: 5



=== TEST 5: certificate does not match host name (verify)
The certificate of "openresty.org" does not contain the name "blah.openresty.org".
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 5;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "blah.openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
            else
                ngx.say("ssl handshake: ", type(session))
            end

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response_like chomp
\Aconnected: 1
failed to do SSL handshake: (?:handshake failed|certificate host mismatch)
failed to send stream request: closed
\z

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
stream lua ssl server name: "blah.openresty.org"
--- no_error_log
SSL reused session
[alert]
--- timeout: 5



=== TEST 6: certificate does not match host name (verify, no log socket errors)
The certificate for "openresty.org" does not contain the name "blah.openresty.org".
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_socket_log_errors off;
    lua_ssl_verify_depth 2;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "blah.openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
            else
                ngx.say("ssl handshake: ", type(session))
            end

            local req = "GET / HTTP/1.1\r\nHost: blah.openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response_like chomp
\Aconnected: 1
failed to do SSL handshake: (?:handshake failed|certificate host mismatch)
failed to send stream request: closed
\z

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
lua ssl server name: "blah.openresty.org"
--- no_error_log
lua ssl certificate does not match host
SSL reused session
[alert]
--- timeout: 5



=== TEST 7: certificate does not match host name (no verify)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", false)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET /en/linux-packages.html HTTP/1.1\r\nHost: openresty.com\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send http request: ", err)
                return
            end

            ngx.say("sent http request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
ssl handshake: userdata
sent http request: 80 bytes.
received: HTTP/1.1 404 Not Found
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/

--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 8: openresty.org: passing SSL verify
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 2;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/

--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 9: ssl verify depth not enough (with automatic error logging)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 0;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
            else
                ngx.say("ssl handshake: ", type(session))
            end

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response eval
qr{connected: 1
failed to do SSL handshake: (22: certificate chain too long|20: unable to get local issuer certificate|21: unable to verify the first certificate)
failed to send stream request: closed
}

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log eval
['lua ssl server name: "openresty.org"',
qr/lua ssl certificate verify error: \((22: certificate chain too long|20: unable to get local issuer certificate|21: unable to verify the first certificate)\)/]
--- no_error_log
SSL reused session
[alert]
--- timeout: 5



=== TEST 10: ssl verify depth not enough (without automatic error logging)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 0;
    lua_socket_log_errors off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(3000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
            else
                ngx.say("ssl handshake: ", type(session))
            end

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response eval
qr/connected: 1
failed to do SSL handshake: (22: certificate chain too long|20: unable to get local issuer certificate|21: unable to verify the first certificate)
failed to send stream request: closed
/

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
lua ssl certificate verify error
SSL reused session
[alert]
--- timeout: 7



=== TEST 11: www.google.com  (SSL verify passes)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 3;

    content_by_lua '
            -- avoid flushing google in "check leak" testing mode:
            local counter = package.loaded.counter
            if not counter then
                counter = 1
            elseif counter >= 2 then
                return ngx.exit(503)
            else
                counter = counter + 1
            end
            package.loaded.counter = counter

            do
                local sock = ngx.socket.tcp()
                sock:settimeout(2000)
                local ok, err = sock:connect("www.google.com", 443)
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ngx.say("connected: ", ok)

                local sess, err = sock:sslhandshake(nil, "www.google.com", true)
                if not sess then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(sess))

                local req = "GET / HTTP/1.1\\r\\nHost: www.google.com\\r\\nConnection: close\\r\\n\\r\\n"
                local bytes, err = sock:send(req)
                if not bytes then
                    ngx.say("failed to send http request: ", err)
                    return
                end

                ngx.say("sent http request: ", bytes, " bytes.")

                local line, err = sock:receive()
                if not line then
                    ngx.say("failed to receive response status line: ", err)
                    return
                end

                ngx.say("received: ", line)

                local ok, err = sock:close()
                ngx.say("close: ", ok, " ", err)
            end  -- do
            collectgarbage()
        ';

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::GoogleRootCertificate"

--- stream_response_like chop
\Aconnected: 1
ssl handshake: userdata
sent http request: 59 bytes.
received: HTTP/1.1 (?:200 OK|302 Found)
close: 1 nil
\z
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log
lua ssl server name: "www.google.com"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 12: www.google.com  (SSL verify enabled and no corresponding trusted certificates)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 3;

    content_by_lua_block {
        -- avoid flushing google in "check leak" testing mode:
        local counter = package.loaded.counter
        if not counter then
            counter = 1
        elseif counter >= 2 then
            return ngx.exit(503)
        else
            counter = counter + 1
        end
        package.loaded.counter = counter

        do
            local sock = ngx.socket.tcp()
            sock:settimeout(2000)
            local ok, err = sock:connect("www.google.com", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(nil, "www.google.com", true)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))

            local req = "GET / HTTP/1.1\\r\\nHost: www.google.com\\r\\nConnection: close\\r\\n\\r\\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
connected: 1
failed to do SSL handshake: 20: unable to get local issuer certificate

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
lua ssl server name: "www.google.com"
lua ssl certificate verify error: (20: unable to get local issuer certificate)
--- no_error_log
SSL reused session
[alert]
--- timeout: 5



=== TEST 13: openresty.org: passing SSL verify with multiple certificates
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 2;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/

--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 14: default cipher
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log eval
[
'lua ssl server name: "openresty.org"',
qr/SSL: TLSv1\.2, cipher: "(?:ECDHE-RSA-AES(?:256|128)-GCM-SHA(?:384|256)|ECDHE-(?:RSA|ECDSA)-CHACHA20-POLY1305) TLSv1\.2/,
]
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 15: explicit cipher configuration
--- http_config
    server {
        listen              unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name         test.com;
        ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;
        ssl_protocols       TLSv1;

        location / {
            content_by_lua_block {
                ngx.exit(200)
            }
        }
    }
--- stream_server_config
    lua_ssl_ciphers ECDHE-RSA-AES256-SHA;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "test.com")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: test.com\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 53 bytes.
received: HTTP/1.1 200 OK
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log eval
['lua ssl server name: "test.com"',
qr/SSL: TLSv\d(?:\.\d)?, cipher: "ECDHE-RSA-AES256-SHA (SSLv3|TLSv1)/]
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 10



=== TEST 16: explicit ssl protocol configuration
--- http_config
    server {
        listen              unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name         test.com;
        ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;
        ssl_protocols       TLSv1;

        location / {
            content_by_lua_block {
                ngx.exit(200)
            }
        }
    }
--- stream_server_config
    lua_ssl_protocols TLSv1;

    content_by_lua '
            local sock = ngx.socket.tcp()
            sock:settimeout(2000)

            do
                local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ngx.say("connected: ", ok)

                local session, err = sock:sslhandshake(nil, "test.com")
                if not session then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(session))

                local req = "GET / HTTP/1.1\\r\\nHost: test.com\\r\\nConnection: close\\r\\n\\r\\n"
                local bytes, err = sock:send(req)
                if not bytes then
                    ngx.say("failed to send stream request: ", err)
                    return
                end

                ngx.say("sent stream request: ", bytes, " bytes.")

                local line, err = sock:receive()
                if not line then
                    ngx.say("failed to receive response status line: ", err)
                    return
                end

                ngx.say("received: ", line)

                local ok, err = sock:close()
                ngx.say("close: ", ok, " ", err)
            end  -- do
            collectgarbage()
        ';
--- config
    server_tokens off;
--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 53 bytes.
received: HTTP/1.1 200 OK
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log eval
[
'lua ssl server name: "test.com"',
qr/SSL: TLSv1, cipher: "ECDHE-RSA-AES256-SHA (SSLv3|TLSv1)/
]
--- no_error_log
SSL reused session
[error]
[alert]



=== TEST 17: unsupported ssl protocol
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_protocols SSLv2;
    lua_socket_log_errors off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
            else
                ngx.say("ssl handshake: ", type(session))
            end

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed
failed to send stream request: closed

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log eval
[
qr/\[(crit|error)\] .*?SSL_do_handshake\(\) failed .*?(unsupported protocol|no protocols available)/,
'lua ssl server name: "openresty.org"',
]
--- no_error_log
SSL reused session
[alert]
[emerg]
--- timeout: 5



=== TEST 18: openresty.org: passing SSL verify: keepalive (reuse the ssl session)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 2;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do

        local session
        for i = 1, 3 do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            session, err = sock:sslhandshake(session, "openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local ok, err = sock:setkeepalive()
            ngx.say("set keepalive: ", ok, " ", err)
        end  -- do

        end
        collectgarbage()
    }

--- config
    server_tokens off;

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
connected: 1
ssl handshake: userdata
set keepalive: 1 nil
connected: 1
ssl handshake: userdata
set keepalive: 1 nil
connected: 1
ssl handshake: userdata
set keepalive: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: \1
$/

--- error_log
lua tcp socket get keepalive peer: using connection
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 19: openresty.org: passing SSL verify: keepalive (no reusing the ssl session)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 2;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do

        local sessions = {}

        for i = 1, 3 do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", true)
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            sessions[i] = session

            ngx.say("ssl handshake: ", type(session))

            local ok, err = sock:setkeepalive()
            ngx.say("set keepalive: ", ok, " ", err)
            ngx.sleep(0.001)
        end  -- do

        end
        collectgarbage()
    }

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
connected: 1
ssl handshake: userdata
set keepalive: 1 nil
connected: 1
ssl handshake: userdata
set keepalive: 1 nil
connected: 1
ssl handshake: userdata
set keepalive: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/stream lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^stream lua ssl save session: ([0-9A-F]+)
stream lua ssl save session: \1
stream lua ssl save session: \1
stream lua ssl free session: \1
stream lua ssl free session: \1
stream lua ssl free session: \1
$/

--- error_log
lua tcp socket get keepalive peer: using connection
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 20: downstream cosockets do not support ssl handshake
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 2;

    content_by_lua_block {
        local sock = ngx.req.socket()
        local sess, err = sock:sslhandshake()
        if not sess then
            ngx.say("failed to do ssl handshake: ", err)
        else
            ngx.say("ssl handshake: ", type(sess))
        end
    }

--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
attempt to call method 'sslhandshake' (a nil value)
--- no_error_log
[alert]
--- timeout: 3



=== TEST 21: unix domain ssl cosocket (no verify)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
            ngx.say("the end...")
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

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

            local sess, err = sock:sslhandshake()
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))

            local req = "thunder!\n";
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to recieve response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 9 bytes.
received: flash!
received: the end...
close: 1 nil

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- no_error_log
lua ssl server name:
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 22: unix domain ssl cosocket (verify)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
            ngx.say("the end...")
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/test.crt;


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

            local req = "thunder!\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to recieve response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 9 bytes.
received: flash!
received: the end...
close: 1 nil

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log
lua ssl server name: "test.com"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 23: unix domain ssl cosocket (no ssl on server)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
            ngx.say("the end...")
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

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

            local sess, err = sock:sslhandshake()
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))

            local req = "thunder!\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to recieve response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed

--- user_files eval
">>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log eval
qr/SSL_do_handshake\(\) failed .*?(unknown protocol|wrong version number)/
--- no_error_log
lua ssl server name:
SSL reused session
[alert]
--- timeout: 3



=== TEST 24: lua_ssl_crl
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_crl ../html/test.crl;
    lua_ssl_trusted_certificate ../html/test.crt;
    lua_socket_log_errors off;

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
            else
                ngx.say("ssl handshake: ", type(sess))
            end

            local req = "thunder!\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to recieve response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response eval
# Since nginx version 1.19.1, invalidity date is considerd a non-critical CRL
# entry extension, in other words, revoke still works even if CRL has expired.
$Test::Nginx::Util::NginxVersion >= 1.019001 ?

"connected: 1
failed to do SSL handshake: 23: certificate revoked
failed to send stream request: closed\n" :

"connected: 1
failed to do SSL handshake: 12: CRL has expired
failed to send stream request: closed\n";

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate
>>> test.crl
$::TestCRL"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
lua ssl server name: "test.com"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 25: multiple handshake calls
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()

        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            for i = 1, 2 do
                local session, err = sock:sslhandshake(nil, "openresty.org")
                if not session then
                    ngx.say("failed to do SSL handshake: ", err)
                    return
                end

                ngx.say("ssl handshake: ", type(session))
            end

            local req = "GET / HTTP/1.1\r\nHost: openresty.org\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
ssl handshake: userdata
ssl handshake: userdata
sent stream request: 58 bytes.
received: HTTP/1.1 302 Moved Temporarily
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 26: handshake timed out
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()

        sock:settimeout(2000)

        do
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            sock:settimeout(1);  -- should timeout immediately
            local session, err = sock:sslhandshake(nil, "openresty.org")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
failed to do SSL handshake: timeout

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
lua ssl server name: "openresty.org"
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 27: unix domain ssl cosocket (no gen session)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
            ngx.say("the end...")
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

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

            local sess, err = sock:sslhandshake(false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", sess)

            sock:close()
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
ssl handshake: true

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- no_error_log
lua ssl server name:
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 28: unix domain ssl cosocket (gen session, true)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
            ngx.say("the end...")
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

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

            local sess, err = sock:sslhandshake(true)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(sess))

            sock:close()
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- no_error_log
lua ssl server name:
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 29: unix domain ssl cosocket (keepalive)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(3000)
        for i = 1, 2 do
            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local sess, err = sock:sslhandshake(false)
            if not sess then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", sess)

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set keepalive: ", err)
                return
            end
        end  -- do
        collectgarbage()
    }

--- config
    server_tokens off;

--- stream_response
connected: 1
ssl handshake: true
connected: 1
ssl handshake: true

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- no_error_log
lua ssl server name:
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 30: unix domain ssl cosocket (verify cert but no host name check, passed)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
            ngx.say("the end...")
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/test.crt;


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

            local req = "thunder!\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to recieve response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 9 bytes.
received: flash!
received: the end...
close: 1 nil

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 5



=== TEST 31: unix domain ssl cosocket (verify cert but no host name check, NOT passed)
--- stream_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        ssl_certificate ../html/test.crt;
        ssl_certificate_key ../html/test.key;

        content_by_lua_block {
            local sock = assert(ngx.req.socket(true))
            local data = sock:receive()
            if data == "thunder!" then
                ngx.say("flash!")
            else
                ngx.say("boom!")
            end
        }
    }
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    #lua_ssl_trusted_certificate ../html/test.crt;


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

            local req = "thunder"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            while true do
                local line, err = sock:receive()
                if not line then
                    -- ngx.say("failed to recieve response status line: ", err)
                    break
                end

                ngx.say("received: ", line)
            end

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
failed to do SSL handshake: 18: self signed certificate

--- user_files eval
">>> test.key
$::TestCertificateKey
>>> test.crt
$::TestCertificate"

--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log
lua ssl certificate verify error: (18: self signed certificate)
--- no_error_log
SSL reused session
[alert]
--- timeout: 5



=== TEST 32: default cipher - TLSv1.3
--- skip_openssl: 8: < 1.1.1
--- http_config
    server {
        listen              unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name         test.com;
        ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;
        ssl_protocols       TLSv1.3;

        location / {
            content_by_lua_block {
                ngx.exit(200)
            }
        }
    }
--- stream_server_config
    lua_ssl_protocols TLSv1.3;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "test.com")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: test.com\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 53 bytes.
received: HTTP/1.1 200 OK
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log eval
[
'lua ssl server name: "test.com"',
qr/SSL: TLSv1.3, cipher: "TLS_AES_256_GCM_SHA384 TLSv1.3/,
]
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 10



=== TEST 33: explicit cipher configuration - TLSv1.3
--- skip_openssl: 8: < 1.1.1
--- skip_nginx: 8: < 1.19.4
--- http_config
    server {
        listen              unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name         test.com;
        ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;
        ssl_protocols       TLSv1.3;

        location / {
            content_by_lua_block {
                ngx.exit(200)
            }
        }
    }
--- stream_server_config
    lua_ssl_protocols TLSv1.3;
    lua_ssl_conf_command Ciphersuites TLS_AES_128_GCM_SHA256;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "test.com")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: test.com\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
ssl handshake: userdata
sent stream request: 53 bytes.
received: HTTP/1.1 200 OK
close: 1 nil

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out eval
qr/^lua ssl save session: ([0-9A-F]+)
lua ssl free session: ([0-9A-F]+)
$/
--- error_log eval
['lua ssl server name: "test.com"',
qr/SSL: TLSv1.3, cipher: "TLS_AES_128_GCM_SHA256 TLSv1.3/]
--- no_error_log
SSL reused session
[error]
[alert]
--- timeout: 10



=== TEST 34: explicit cipher configuration not in the default list - TLSv1.3
--- skip_openssl: 8: < 1.1.1
--- skip_nginx: 8: < 1.19.4
--- http_config
    server {
        listen              unix:$TEST_NGINX_HTML_DIR/nginx.sock ssl;
        server_name         test.com;
        ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;
        ssl_protocols       TLSv1.3;

        location / {
            content_by_lua_block {
                ngx.exit(200)
            }
        }
    }
--- stream_server_config
    lua_ssl_protocols TLSv1.3;
    lua_ssl_conf_command Ciphersuites TLS_AES_128_CCM_SHA256;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(2000)

        do
            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local session, err = sock:sslhandshake(nil, "test.com")
            if not session then
                ngx.say("failed to do SSL handshake: ", err)
                return
            end

            ngx.say("ssl handshake: ", type(session))

            local req = "GET / HTTP/1.1\r\nHost: test.com\r\nConnection: close\r\n\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send stream request: ", err)
                return
            end

            ngx.say("sent stream request: ", bytes, " bytes.")

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to recieve response status line: ", err)
                return
            end

            ngx.say("received: ", line)

            local ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end  -- do
        collectgarbage()
    }

--- stream_response
connected: 1
failed to do SSL handshake: handshake failed

--- log_level: debug
--- grep_error_log eval: qr/lua ssl (?:set|save|free) session: [0-9A-F]+/
--- grep_error_log_out
--- error_log eval
[
qr/\[info\] .*?SSL_do_handshake\(\) failed .*?no shared cipher/,
'lua ssl server name: "test.com"',
]
--- no_error_log
SSL reused session
[alert]
[emerg]
--- timeout: 10
