# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(3);

# All these tests need to have new openssl
my $NginxBinary = $ENV{'TEST_NGINX_BINARY'} || 'nginx';
my $openssl_version = eval { `$NginxBinary -V 2>&1` };

if ($openssl_version =~ m/built with OpenSSL (0\S*|1\.0\S*|1\.1\.0\S*)/) {
    plan(skip_all => "too old OpenSSL, need 1.1.1, was $1");
} else {
    plan tests => repeat_each() * (blocks() * 7);
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
        #listen 127.0.0.1:4433 ssl;
        ssl_client_hello_by_lua_block { print("ssl client hello by lua is running!") }
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;
        #ssl_trusted_certificate ../../cert/test.crt;
        ssl_client_certificate ../../cert/test.crt;
        ssl_verify_client on;
        ssl_protocols TLSv1 TLSv1.1 TLSv1.2;

        log_by_lua_block {
            ngx.log(ngx.INFO, "ssl_client_s_dn: ", ngx.var.ssl_client_s_dn)
        }
        return 'it works!\n';
    }
--- stream_server_config
    lua_ssl_certificate ../../cert/test.crt;
    lua_ssl_certificate_key ../../cert/test.key;
    lua_ssl_trusted_certificate ../../cert/test.crt;

    content_by_lua_block {
        do
            local sock = ngx.socket.tcp()

            sock:settimeout(2000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock")
            -- local ok, err = sock:connect("127.0.0.1", 4433)
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
ssl_client_s_dn: emailAddress=agentzh@gmail.com,CN=test.com,OU=OpenResty,O=OpenResty,L=San Francisco,ST=California,C=US

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
