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

our $UpstreamSrvConfig = <<_EOC_;
    server {
        listen                  127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT} ssl;
        listen                  127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT} ssl;

        ssl_certificate         $ENV{TEST_NGINX_CERT_DIR}/cert/test.crt;
        ssl_certificate_key     $ENV{TEST_NGINX_CERT_DIR}/cert/test.key;
        ssl_session_tickets     off;
        ssl_verify_client       optional_no_ca;

        keepalive_requests 1000;

        location = /echo_client_addr {
            content_by_lua_block {
                ngx.say(ngx.var.remote_addr)
            }
        }

        location = /echo_client_addr_port {
            content_by_lua_block {
                ngx.say(ngx.var.remote_addr, ":", ngx.var.remote_port)
            }
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
        $block->set_value("grep_error_log", qr/lua balancer: keepalive (?!closing).*/);
    }

    if (!defined $block->no_error_log) {
        $block->set_value("no_error_log", "[error]");
    }
});

log_level('debug');
no_long_string();
run_tests();

__DATA__

=== TEST 1: get keepalive from pool
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            ok, err = b.bind_to_local_addr("127.0.0.11")
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
    }
"
--- response_body
127.0.0.11
127.0.0.11
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/



=== TEST 2: get keepalive from pool twice
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            ok, err = b.bind_to_local_addr("127.0.0.11")
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
    }
"
--- response_body
127.0.0.11
127.0.0.11
127.0.0.11
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/



=== TEST 3: can not get idle connection from the pool
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            local src_ip = ngx.var.arg_src_ip or "127.0.0.1"
            ok, err = b.bind_to_local_addr(src_ip)
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2&src_ip=127.0.0.10';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2&src_ip=127.0.0.11';
    }
"
--- response_body
127.0.0.10
127.0.0.11
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/



=== TEST 4: et idle connections from the pool for different src ip
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            local src_ip = ngx.var.arg_src_ip or "127.0.0.1"
            ok, err = b.bind_to_local_addr(src_ip)
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2&src_ip=127.0.0.10';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2&src_ip=127.0.0.11';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2&src_ip=127.0.0.11';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2&src_ip=127.0.0.10';
    }
"
--- response_body
127.0.0.10
127.0.0.11
127.0.0.11
127.0.0.10
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/



=== TEST 5: should not use idle connection with different dest ip
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            ok, err = b.bind_to_local_addr("127.0.0.11")
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.1';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
    }
"
--- response_body
127.0.0.11
127.0.0.11
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.1:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/



=== TEST 6: empty host
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            ok, err = b.bind_to_local_addr("127.0.0.11")
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_client_addr' -q 'ip=127.0.0.2';
    }
"
--- response_body
127.0.0.11
127.0.0.11
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/



=== TEST 7: bind addr with port
--- http_upstream
    upstream test_upstream {
        server 0.0.0.1;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local ip = ngx.var.arg_ip or "127.0.0.1"
            local port = ngx.var.arg_port or $TEST_NGINX_SERVER_SSL_PORT

            local ok, err = b.set_current_peer(ip, port, "test.com")
            if not ok then
                ngx.log(ngx.ERR, "failed to set current peer: ", err)
                return
            end

            local ok, err = b.enable_keepalive()
            if not ok then
                ngx.log(ngx.ERR, "failed to set keepalive: ", err)
                return
            end

            ok, err = b.bind_to_local_addr("127.0.0.11:64321")
            if not ok then
                ngx.log(ngx.ERR, "failed to set local addr: ", err)
                return
            end
        }
    }
--- config eval
"
    location = /t {
        echo_subrequest GET '/proxy/echo_client_addr_port' -q 'ip=127.0.0.2';
        echo_subrequest GET '/proxy/echo_client_addr_port' -q 'ip=127.0.0.2';
    }
"
--- response_body
127.0.0.11:64321
127.0.0.11:64321
--- grep_error_log_out eval
qr/^lua balancer: keepalive no free connection, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive reusing connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
lua balancer: keepalive saving connection [0-9A-F]+, host: 127.0.0.2:$ENV{TEST_NGINX_SERVER_SSL_PORT}, name: test.com
$/
