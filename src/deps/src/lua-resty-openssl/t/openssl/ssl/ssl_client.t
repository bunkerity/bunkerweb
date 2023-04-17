# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


repeat_each(2);

my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

add_block_preprocessor(sub {
    my ($block) = @_;

    my $name = $block->name;

    my $http_config = $block->http_config;

    if (defined $http_config ) {

        my $new_http_config = <<_EOC_;
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";

    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end
        _G.myassert = require("helper").myassert
        _G.encode_sorted_json = require("helper").encode_sorted_json
    }

    ssl_certificate $pwd/t/fixtures/test.crt;
    ssl_certificate_key $pwd/t/fixtures/test.key;

    lua_ssl_trusted_certificate $pwd/t/fixtures/test.crt;

$http_config

_EOC_

        $block->set_value("http_config", $new_http_config);
    }

});


our $ClientContentBy = qq{

};

no_long_string();

env_to_nginx("CI_SKIP_NGINX_C");

run_tests();

__DATA__
=== TEST 1: SSL (client) get peer certificate
--- http_config
    server {
        listen unix:/tmp/nginx-c1.sock ssl;
        server_name   test.com;
    }
--- config
    location /t {
        content_by_lua_block {
            local sock = ngx.socket.tcp()
            myassert(sock:connect("unix:/tmp/nginx-c1.sock"))
            myassert(sock:sslhandshake(nil, "test.com"))
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_socket(sock))

            local crt = myassert(sess:get_peer_certificate())
            ngx.say(myassert(crt:get_subject_name():tostring()))
        }
    }
--- request
    GET /t
--- response_body
CN=test.com

--- no_error_log
[error]
[emerg]


=== TEST 2: SSL (client) get peer cert chain
--- http_config
    server {
        listen unix:/tmp/nginx-c2.sock ssl;
        server_name   test.com;
    }
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
            local sock = ngx.socket.tcp()
            myassert(sock:connect("unix:/tmp/nginx-c2.sock"))
            myassert(sock:sslhandshake(nil, "test.com"))
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_socket(sock))

            local chain = myassert(sess:get_peer_cert_chain())
            ngx.say(#chain)
            local crt = chain[1]
            ngx.say(myassert(crt:get_subject_name():tostring()))
        }
    }
--- request
    GET /t
--- response_body
1
CN=test.com

--- no_error_log
[error]
[emerg]

=== TEST 3: SSL (client) set cipher suites [skipped]
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
        }
    }
--- request
    GET /t
--- skip_nginx
2: < 9.9.9
--- response_body
--- no_error_log
[error]
[emerg]

=== TEST 4: SSL (client) get ciphers
--- http_config
    server {
        listen unix:/tmp/nginx-c4.sock ssl;
        server_name   test.com;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384;
    }
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
            local sock = ngx.socket.tcp()
            myassert(sock:connect("unix:/tmp/nginx-c4.sock"))
            myassert(sock:sslhandshake(nil, "test.com"))
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_socket(sock))

            ngx.say(myassert(sess:get_ciphers()))

            local cipher = myassert(sess:get_cipher_name())
            ngx.say(cipher)
        }
    }
--- request
    GET /t
--- response_body_like
.*ECDHE-RSA-AES256-GCM-SHA384.*
ECDHE-RSA-AES256-GCM-SHA384

--- no_error_log
[error]
[emerg]

=== TEST 5: SSL (client) get/set timeout
--- http_config
    server {
        listen unix:/tmp/nginx-c5.sock ssl;
        server_name   test.com;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384;
    }
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
            local sock = ngx.socket.tcp()
            myassert(sock:connect("unix:/tmp/nginx-c5.sock"))
            myassert(sock:sslhandshake(nil, "test.com"))
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_socket(sock))

            ngx.say(myassert(sess:get_timeout()))
            myassert(sess:set_timeout(15))
            ngx.say(myassert(sess:get_timeout()))
        }
    }
--- request
    GET /t
--- response_body_like
\d+
15

--- no_error_log
[error]
[emerg]

=== TEST 6: SSL (client) set_verify and add_client_ca [skipped]
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
        }
    }
--- request
    GET /t
--- skip_nginx
2: < 9.9.9
--- response_body
--- no_error_log
[error]
[emerg]

=== TEST 7: SSL (client) set/get/clear options
--- http_config
    server {
        listen unix:/tmp/nginx-c7.sock ssl;
        server_name   test.com;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384;
    }
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
            local sock = ngx.socket.tcp()
            myassert(sock:connect("unix:/tmp/nginx-c7.sock"))
            myassert(sock:sslhandshake(nil, "test.com"))
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_socket(sock))

            local orig_options = myassert(sess:get_options())
            ngx.say(orig_options)
            ngx.say(require("cjson").encode(myassert(sess:get_options(true))))

            myassert(sess:set_options(ssl.SSL_OP_PRIORITIZE_CHACHA))
            myassert(sess:set_options(ssl.SSL_OP_ALLOW_NO_DHE_KEX, ssl.SSL_OP_NO_QUERY_MTU))
            ngx.say(require("cjson").encode(myassert(sess:get_options(true))))

            myassert(sess:clear_options(ssl.SSL_OP_PRIORITIZE_CHACHA))
            myassert(sess:clear_options(ssl.SSL_OP_ALLOW_NO_DHE_KEX, ssl.SSL_OP_NO_QUERY_MTU))
            local new_options = myassert(sess:get_options())
            if new_options ~= orig_options then
                ngx.say("options not correct after clear: " ..
                        require("cjson").encode(myassert(sess:get_options(true))))
            else
                ngx.say("ok")
            end
        }
    }
--- request
    GET /t
--- response_body_like
\d+
\[".+"\]
.+SSL_OP_ALLOW_NO_DHE_KEX.+SSL_OP_NO_QUERY_MTU.+SSL_OP_PRIORITIZE_CHACHA.+
ok

--- no_error_log
[error]
[emerg]

=== TEST 8: SSL (client) set_protocols [skipped]
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
        }
    }
--- request
    GET /t
--- skip_nginx
2: < 9.9.9
--- response_body
--- no_error_log
[error]
[emerg]

