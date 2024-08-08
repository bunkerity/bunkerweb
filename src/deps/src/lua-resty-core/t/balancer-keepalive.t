# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

my $NginxBinary = $ENV{TEST_NGINX_BINARY} || 'nginx';
my $NginxV = eval { `$NginxBinary -V 2>&1` };

if ($NginxV !~ m/built with OpenSSL/) {
    plan(skip_all => "OpenSSL required");

} elsif ($NginxV !~ m/--with-debug/) {
    plan(skip_all => "--with-debug required");

} else {
    plan tests => repeat_each() * (blocks() * 4);
}

$ENV{TEST_NGINX_SERVER_SSL_PORT_2} = get_unused_port $ENV{TEST_NGINX_SERVER_SSL_PORT} + 1;

our $UpstreamSrvConfig = <<_EOC_;
    server {
        listen                  127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT} ssl;
        listen                  127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT} ssl;
        listen                  127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT_2} ssl;

        ssl_certificate         $ENV{TEST_NGINX_CERT_DIR}/cert/test.crt;
        ssl_certificate_key     $ENV{TEST_NGINX_CERT_DIR}/cert/test.key;
        ssl_session_tickets     off;
        ssl_verify_client       optional_no_ca;

        keepalive_requests 1000;

        location = /echo_sni {
            return 200 'SNI=\$ssl_server_name\\n';
        }

        location = /echo_ssl_client_s_dn_and_protocol {
            return 200 'ssl_client_s_dn=\$ssl_client_s_dn ssl_protocol=\$ssl_protocol\\n';
        }

        location = /close {
            add_header Connection close;
            return 200;
        }

        location = /short_keepalive {
            keepalive_timeout 100ms;
            return 200;
        }

        location = /sleep {
            echo_sleep 0.3;
            echo_status 200;
        }

        location / {
            return 200;
        }
    }
_EOC_

our $ProxyLocConfig = <<_EOC_;
    location ~ ^/proxy/(?<upstream_uri>.*) {
        proxy_ssl_verify      off;
        proxy_ssl_server_name on;
        proxy_ssl_name        '\$arg_sni';

        proxy_http_version    1.1;
        proxy_set_header      Connection '';
        proxy_pass            https://test_upstream/\$upstream_uri;
    }

    location ~ ^/proxy_lua_sni/(?<upstream_uri>.*) {
        proxy_ssl_verify      off;
        proxy_ssl_server_name on;
        #proxy_ssl_name        '\$arg_sni';

        proxy_http_version    1.1;
        proxy_set_header      Connection '';
        proxy_pass            https://test_upstream/\$upstream_uri;
    }
_EOC_

add_block_preprocessor(sub {
    my $block = shift;

    if (defined $block->http_upstream) {
        $block->set_value("http_config",
                          $block->http_upstream . "\n" . $UpstreamSrvConfig);
    }

    if (defined $block->config) {
        $block->set_value("config",
                          $block->config . "\n" . $ProxyLocConfig);

    } else {
        $block->set_value("config", $ProxyLocConfig);
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }

    if (!defined $block->grep_error_log) {
        $block->set_value("grep_error_log", qr/lua balancer: keepalive .*/);
    }

    if (!defined $block->no_error_log) {
        $block->set_value("no_error_log", "[error]");
    }
});

log_level('debug');
no_long_string();
run_tests();

__DATA__

=== TEST 1: upstream_keepalive_module: sanity (nginx default)
--- http_upstream
    upstream test_upstream {
        server 127.0.0.1:$TEST_NGINX_SERVER_SSL_PORT;
        keepalive 60;
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
    }
--- response_body
SNI=one
SNI=one
--- grep_error_log_out



=== TEST 2: enable_keepalive: sanity (different ip port)
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two&ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=three&ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=three&ip=127.0.0.2&port=$ENV{TEST_NGINX_SERVER_SSL_PORT_2}';
    }
"
--- response_body
SNI=one
SNI=two
SNI=two
SNI=three
SNI=three
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: three
lua balancer: keepalive saving connection \S+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: three
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT_2}, name: three
lua balancer: keepalive saving connection \S+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT_2}, name: three$/



=== TEST 3: enable_keepalive: sanity(same ip port with different sni)
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local pool
            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=three';
    }
--- response_body
SNI=one
SNI=two
SNI=three
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: three
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: three/



=== TEST 4: enable_keepalive: sanity
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two&ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=three&ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=three&ip=127.0.0.2&port=$ENV{TEST_NGINX_SERVER_SSL_PORT_2}';
    }
"
--- response_body
SNI=one
SNI=two
SNI=two
SNI=three
SNI=three
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: three
lua balancer: keepalive saving connection \S+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: three
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT_2}, name: three
lua balancer: keepalive saving connection \S+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT_2}, name: three$/



=== TEST 5: enable_keepalive: sanity (dynamic sni option)
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1",
                                               $TEST_NGINX_SERVER_SSL_PORT,
                                               ngx.var.arg_sni)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy_lua_sni/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy_lua_sni/echo_sni' -q 'sni=two';
    }
--- response_body
SNI=one
SNI=two
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
$/



=== TEST 6: upstream_keepalive_module: no granular pooling (TLS properties)
--- http_upstream
    upstream test_upstream {
        server 127.0.0.1:$TEST_NGINX_SERVER_SSL_PORT;
        keepalive 60;
    }
--- config
    proxy_ssl_verify              off;
    proxy_http_version            1.1;
    proxy_set_header              Connection '';

    location ~ ^/client_one/tls11/proxy/(?<upstream_uri>.*) {
        proxy_ssl_protocols       TLSv1.1;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location ~ ^/client_one/tls12/proxy/(?<upstream_uri>.*) {
        proxy_ssl_protocols       TLSv1.2;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location ~ ^/client_two/tls11/proxy/(?<upstream_uri>.*) {
        proxy_ssl_protocols       TLSv1.1;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test2.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test2.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location ~ ^/client_two/tls12/proxy/(?<upstream_uri>.*) {
        proxy_ssl_protocols       TLSv1.2;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test2.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test2.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location = /t {
        echo_subrequest GET '/client_one/tls11/proxy/echo_ssl_client_s_dn_and_protocol';
        echo_subrequest GET '/client_one/tls12/proxy/echo_ssl_client_s_dn_and_protocol';
        echo_subrequest GET '/client_two/tls11/proxy/echo_ssl_client_s_dn_and_protocol';
        echo_subrequest GET '/client_two/tls12/proxy/echo_ssl_client_s_dn_and_protocol';
    }
--- response_body_like
ssl_client_s_dn=.*?CN=test\.com.*? ssl_protocol=TLSv1\.1
ssl_client_s_dn=.*?CN=test\.com.*? ssl_protocol=TLSv1\.1
ssl_client_s_dn=.*?CN=test\.com.*? ssl_protocol=TLSv1\.1
ssl_client_s_dn=.*?CN=test\.com.*? ssl_protocol=TLSv1\.1
--- grep_error_log_out



=== TEST 7: enable_keepalive: do not support reuse by TLS properties
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1",
                                $TEST_NGINX_SERVER_SSL_PORT,
                                ngx.var.client_cert)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    proxy_ssl_verify              off;
    proxy_http_version            1.1;
    proxy_set_header              Connection '';

    location ~ ^/client_one/tls11/proxy/(?<upstream_uri>.*) {
        set                       $client_cert 'test.crt';
        set                       $client_protocol 'TLSv1.1';
        proxy_ssl_protocols       TLSv1.1;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location ~ ^/client_one/tls12/proxy/(?<upstream_uri>.*) {
        set                       $client_cert 'test.crt';
        set                       $client_protocol 'TLSv1.2';
        proxy_ssl_protocols       TLSv1.2;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location ~ ^/client_two/tls11/proxy/(?<upstream_uri>.*) {
        set                       $client_cert 'test2.crt';
        set                       $client_protocol 'TLSv1.1';
        proxy_ssl_protocols       TLSv1.1;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test2.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test2.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location ~ ^/client_two/tls12/proxy/(?<upstream_uri>.*) {
        set                       $client_cert 'test2.crt';
        set                       $client_protocol 'TLSv1.2';
        proxy_ssl_protocols       TLSv1.2;
        proxy_ssl_certificate     $TEST_NGINX_CERT_DIR/cert/test2.crt;
        proxy_ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test2.key;

        proxy_pass                https://test_upstream/$upstream_uri;
    }

    location = /t {
        echo_subrequest GET '/client_one/tls11/proxy/echo_ssl_client_s_dn_and_protocol';
        echo_subrequest GET '/client_one/tls12/proxy/echo_ssl_client_s_dn_and_protocol';
        echo_subrequest GET '/client_two/tls11/proxy/echo_ssl_client_s_dn_and_protocol';
        echo_subrequest GET '/client_two/tls12/proxy/echo_ssl_client_s_dn_and_protocol';
    }
--- response_body_like
ssl_client_s_dn=.*?CN=test\.com.*? ssl_protocol=TLSv1\.1
ssl_client_s_dn=.*?CN=test\.com.*? ssl_protocol=TLSv1\.1
ssl_client_s_dn=.*?CN=test2\.com.*? ssl_protocol=TLSv1\.1
ssl_client_s_dn=.*?CN=test2\.com.*? ssl_protocol=TLSv1\.1
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.crt
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.crt
lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.crt
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.crt
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test2.crt
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test2.crt
lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test2.crt
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test2.crt
$/



=== TEST 8: set_current_peer: bad argument #4 'sni'
--- config
    location = /t {
        content_by_lua_block {
            local b = require "ngx.balancer"

            local values = { true, 0 }

            for _, val in ipairs(values) do
                local pok, perr = pcall(b.set_current_peer, "127.0.0.1", 80, val)
                if not pok then
                    ngx.say(perr)
                end
            end
        }
    }
--- response_body eval
qr{./lib/ngx/balancer.lua:\d+: bad argument #3 to 'set_current_peer' \(string expected, got boolean\)
./lib/ngx/balancer.lua:\d+: bad argument #3 to 'set_current_peer' \(string expected, got number\)}
--- grep_error_log_out



=== TEST 9: set_current_peer: bad option 'pool_size'
--- SKIP
--- config
    location = /t {
        content_by_lua_block {
            local b = require "ngx.balancer"

            local values = { true, 0, -1 }

            for _, val in ipairs(values) do
                local pok, perr = pcall(b.set_current_peer, "127.0.0.1", 80, {
                    pool = "foo",
                    pool_size = val,
                })
                if not pok then
                    ngx.say(perr)
                end
            end
        }
    }
--- response_body
bad option 'pool_size' to 'set_current_peer' (number expected, got boolean)
bad option 'pool_size' to 'set_current_peer' (expected > 0)
bad option 'pool_size' to 'set_current_peer' (expected > 0)
--- grep_error_log_out



=== TEST 10: enable_keepalive: bad usage (no upstream)
--- config
    location = /t {
        content_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
no upstream found
--- grep_error_log_out



=== TEST 11: enable_keepalive: bad usage (bad context)
--- http_upstream
    upstream test_upstream {
        server 127.0.0.1:$TEST_NGINX_SERVER_SSL_PORT;
    }
--- config
    location = /t {
        proxy_pass https://test_upstream/;

        log_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.NOTICE, err)
            end
        }
    }
--- ignore_response_body
--- grep_error_log_out
--- error_log
API disabled in the current context



=== TEST 12: enable_keepalive: bad usage (no current peer)
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
            end

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/';
    }
--- response_body
--- grep_error_log_out
--- no_error_log
--- error_log
failed to set keepalive: no current peer set



=== TEST 13: enable_keepalive: bad argument #1 'idle_timeout'
--- config
    location = /t {
        content_by_lua_block {
            local b = require "ngx.balancer"

            local values = { true, -1 }

            for _, val in ipairs(values) do
                local pok, perr = pcall(b.enable_keepalive, val)
                if not pok then
                    ngx.say(perr)
                end
            end
        }
    }
--- response_body
bad argument #1 to 'enable_keepalive' (number expected, got boolean)
bad argument #1 to 'enable_keepalive' (expected >= 0)
--- grep_error_log_out



=== TEST 14: enable_keepalive: bad argument #2 'max_requests'
--- config
    location = /t {
        content_by_lua_block {
            local b = require "ngx.balancer"

            local values = { true, -1 }

            for _, val in ipairs(values) do
                local pok, perr = pcall(b.enable_keepalive, nil, val)
                if not pok then
                    ngx.say(perr)
                end
            end
        }
    }
--- response_body
bad argument #2 to 'enable_keepalive' (number expected, got boolean)
bad argument #2 to 'enable_keepalive' (expected >= 0)
--- grep_error_log_out



=== TEST 15: enable_keepalive: reaching 'max_requests > 0' closes keepalive connection (and frees empty pool)
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive(nil, 3)
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        set $requests_plan '/,/,/,/';

        echo_foreach_split ',' $requests_plan;
            echo_subrequest GET '/proxy$echo_it';
        echo_end;
    }
--- response_body
--- wait: 0.15
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: $/



=== TEST 16: enable_keepalive: 'max_requests == 100' is the default value
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        content_by_lua_block {
            for i = 1, 100 do
                ngx.location.capture("/proxy/")
            end
        }
    }
--- response_body
--- grep_error_log_out eval
qr/\Alua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
(lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
){98}lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+
\z/



=== TEST 17: enable_keepalive: 'max_requests == 0' never closes upstream connections
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive(nil, 0)
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        content_by_lua_block {
            for i = 1, 100 do
                ngx.location.capture("/proxy/")
            end
        }
    }
--- response_body
--- grep_error_log: lua balancer: keepalive not saving connection
--- grep_error_log_out



=== TEST 18: enable_keepalive: reaching 'idle_timeout > 0' closes keepalive connection (and frees empty pool)
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive(0.1)
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/';
        echo_sleep 0.15;
        echo_subrequest GET '/proxy/';
    }
--- response_body
--- wait: 0.2
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive closing connection \S+
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive closing connection \S+$/



=== TEST 19: enable_keepalive: reaching 'pool_size' closes extra connections
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;
        balancer_keepalive 2;
        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest_async GET '/proxy/';
        echo_subrequest_async GET '/proxy/';
        echo_subrequest_async GET '/proxy/';
        echo_sleep 0.3;
        echo_subrequest_async GET '/proxy/';
        echo_subrequest_async GET '/proxy/';
        echo_subrequest_async GET '/proxy/';
    }
--- response_body
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive closing connection \S+
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive reusing connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive closing connection \S+
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: $/



=== TEST 20: enable_keepalive: keepalive connections can be closed by upstream
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest_async GET '/proxy/short_keepalive';
        echo_subrequest_async GET '/proxy/short_keepalive';
    }
--- wait: 0.15
--- response_body
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive closing connection \S+
lua balancer: keepalive closing connection \S+
$/



=== TEST 21: enable_keepalive: does not save non-keepalive connections
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/close';
        echo_subrequest GET '/proxy/close';
    }
--- response_body
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+
$/



=== TEST 22: enable_keepalive: does not save bad connections
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.3", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/';
    }
--- response_body_like: 502 Bad Gateway
--- no_error_log
--- error_log eval
qr/connect\(\) failed \(\d+: Connection refused\) while connecting to upstream/
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.3:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+$/



=== TEST 23: enable_keepalive: does not save timed out connections
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.set_timeouts(nil, nil, 0.1)
            if not ok then
                ngx.log(ngx.ERR, "failed to set timeouts: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/sleep';
    }
--- response_body_like: 504 Gateway Time-out
--- no_error_log
--- error_log
upstream timed out
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+$/



=== TEST 24: enable_keepalive: can be called again upon retry
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            if not ngx.ctx.tries then
                ngx.ctx.tries = 0

            else
                ngx.ctx.tries = ngx.ctx.tries + 1
            end

            local ip = "127.0.0.3"
            local port = $TEST_NGINX_SERVER_SSL_PORT
            local pool_size = 1

            if ngx.ctx.tries < 1 then
                local ok, err = b.set_more_tries(1)
                if not ok then
                    ngx.log(ngx.ERR, "failed to set more tries: ", err)
                    return
                end

            else
                ip = "127.0.0.1"
                pool_size = 2
            end

            local ok, err = b.set_current_peer(ip, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/';
    }
--- response_body
--- no_error_log
[crit]
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.3:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive not saving connection \S+
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name:\s
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: $/



=== TEST 25: enable_keepalive: must be called for each try
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = "127.0.0.1"
            local port = $TEST_NGINX_SERVER_SSL_PORT

            if not ngx.ctx.tries then
                ngx.ctx.tries = 0

            else
                ngx.ctx.tries = ngx.ctx.tries + 1
            end

            if ngx.var.arg_sni == "one" and ngx.ctx.tries == 0 then
                ip = "127.0.0.3"

                local ok, err = b.set_more_tries(1)
                if not ok then
                    ngx.log(ngx.ERR, "failed to set more tries: ", err)
                    return
                end
            end

            local ok, err = b.set_current_peer(ip, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            if ngx.ctx.tries == 0 then
                local ok, err = b.enable_keepalive()
                if not ok then
                    ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                    return
                end
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
    }
--- response_body
SNI=one
SNI=two
--- no_error_log
[crit]
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.3:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
lua balancer: keepalive not saving connection \S+
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
lua balancer: keepalive saving connection \S+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
$/



=== TEST 26: enable_keepalive: bypasses previous 'keepalive' directive
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;
        keepalive 10;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT, {
                pool = ngx.var.arg_sni,
            })
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
    }
--- response_body
SNI=one
SNI=two
--- grep_error_log eval: qr/(?:lua balancer: keepalive .*|(?:get|free) keepalive peer)/
--- grep_error_log_out eval
qr/^lua balancer: keepalive create pool, crc32: \S+, size: 30
lua balancer: keepalive no free connection, cpool: \S+
lua balancer: keepalive saving connection \S+, cpool: \S+, connections: 1
lua balancer: keepalive create pool, crc32: \d+, size: 30
lua balancer: keepalive no free connection, cpool: \S+
lua balancer: keepalive saving connection \S+, cpool: \S+, connections: 1$/
--- SKIP



=== TEST 27: enable_keepalive: is superseded by a subsequent 'keepalive' directive
In this case, the upstream_keepalive_module pool gets queried but is always
empty, as peers always get saved by the Lua pooling.
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ok, err = b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_SSL_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end
        }

        keepalive 10;
    }
--- config
    location = /t {
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=one';
        echo_subrequest GET '/proxy/echo_sni' -q 'sni=two';
    }
--- response_body
SNI=one
SNI=one
--- grep_error_log eval: qr/(?:lua balancer: keepalive .*|(?:get|free) keepalive peer)/
--- grep_error_log_out eval
qr/^get keepalive peer
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: one
free keepalive peer
free keepalive peer
lua balancer: keepalive not saving connection \S+
get keepalive peer
lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: two
get keepalive peer
free keepalive peer
free keepalive peer
lua balancer: keepalive not saving connection \S+$/
