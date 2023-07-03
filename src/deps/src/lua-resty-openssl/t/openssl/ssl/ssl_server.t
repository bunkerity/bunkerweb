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
=== TEST 1: SSL (server) get peer certificate
--- http_config
    server {
        listen unix:/tmp/nginx-s1.sock ssl;
        server_name   test.com;

        ssl_certificate_by_lua_block {
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_request())
            myassert(sess:set_verify(ssl.SSL_VERIFY_PEER, nil))
        }

        location /t {
            content_by_lua_block {
                local ssl = require "resty.openssl.ssl"
                local sess = myassert(ssl.from_request())

                local crt = myassert(sess:get_peer_certificate())
                ngx.say(myassert(crt:get_subject_name():tostring()))
            }
        }
    }
--- config
    location /t {
        proxy_pass https://unix:/tmp/nginx-s1.sock:;
        proxy_ssl_server_name on;
        proxy_ssl_name test.com;
        # valgrind be happy
        proxy_ssl_session_reuse off;

        proxy_ssl_certificate ../../../t/fixtures/test.crt;
        proxy_ssl_certificate_key ../../../t/fixtures/test.key;
    }
--- request
    GET /t
--- response_body
CN=test.com

--- no_error_log
[error]
[emerg]


=== TEST 2: SSL (server) get peer cert chain
--- http_config
    server {
        listen unix:/tmp/nginx-s2.sock ssl;
        server_name   test.com;

        ssl_certificate_by_lua_block {
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_request())
            myassert(sess:set_verify(ssl.SSL_VERIFY_PEER, nil))
        }

        location /t {
            content_by_lua_block {
                local ssl = require "resty.openssl.ssl"
                local sess = myassert(ssl.from_request())

                local ciphers = myassert(sess:get_ciphers())

                local chain = myassert(sess:get_peer_cert_chain())
                ngx.say(#chain)
            }
        }
    }
--- config
    location /t {
        proxy_pass https://unix:/tmp/nginx-s2.sock:;
        proxy_ssl_server_name on;
        proxy_ssl_name test.com;
        # valgrind be happy
        proxy_ssl_session_reuse off;

        proxy_ssl_certificate ../../../t/fixtures/test.crt;
        proxy_ssl_certificate_key ../../../t/fixtures/test.key;
    }
--- request
    GET /t
--- response_body
0

--- no_error_log
[error]
[emerg]

=== TEST 3: SSL (server) set cipher suites (TLSv1.3 set_ciphersuites not tested)
--- http_config
    server {
        listen unix:/tmp/nginx-s3.sock ssl;
        server_name   test.com;
        ssl_ciphers ECDHE-RSA-AES128-SHA;

        ssl_certificate_by_lua_block {
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_request())

            myassert(sess:set_cipher_list("ECDHE-RSA-AES256-SHA"))
        }

        location /t {
            content_by_lua_block {
                ngx.say("ok")
            }
        }
    }
--- config
    location /t {
        default_type 'text/plain';
        content_by_lua_block {
            local sock = ngx.socket.tcp()
            myassert(sock:connect("unix:/tmp/nginx-s3.sock"))
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
.*ECDHE-RSA-AES256-SHA.*
ECDHE-RSA-AES256-SHA$

--- no_error_log
[error]
[emerg]


=== TEST 4: SSL (server) get ciphers
--- http_config
    server {
        listen unix:/tmp/nginx-s4.sock ssl;
        server_name   test.com;
        ssl_ciphers ECDHE-RSA-AES128-SHA;

        location /t {
            content_by_lua_block {
                local ssl = require "resty.openssl.ssl"
                local sess = myassert(ssl.from_request())

                local ciphers = myassert(sess:get_ciphers())
                ngx.say(ciphers)

                local cipher = myassert(sess:get_cipher_name())
                ngx.say(cipher)
            }
        }
    }
--- config
    location /t {
        proxy_pass https://unix:/tmp/nginx-s4.sock:;
        proxy_ssl_server_name on;
        proxy_ssl_name test.com;
        # valgrind be happy
        proxy_ssl_session_reuse off;
    }
--- request
    GET /t
--- response_body_like
.*ECDHE-RSA-AES128-SHA.*
ECDHE-RSA-AES128-SHA$

--- no_error_log
[error]
[emerg]

=== TEST 5: SSL (server) get/set timeout
--- http_config
    server {
        listen unix:/tmp/nginx-s5.sock ssl;
        server_name   test.com;

        location /t {
            content_by_lua_block {
                local ssl = require "resty.openssl.ssl"
                local sess = myassert(ssl.from_request())

                ngx.say(myassert(sess:get_timeout()))
                myassert(sess:set_timeout(15))
                ngx.say(myassert(sess:get_timeout()))
            }
        }
    }
--- config
    location /t {
        proxy_pass https://unix:/tmp/nginx-s5.sock:;
        proxy_ssl_server_name on;
        proxy_ssl_name test.com;
        # valgrind be happy
        proxy_ssl_session_reuse off;
    }
--- request
    GET /t
--- response_body_like
\d+
15

--- no_error_log
[error]
[emerg]

=== TEST 6: SSL (server) set_verify and add_client_ca [tested in get_peer_cert]
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

=== TEST 7: SSL (server) get/set/clear options
--- http_config
    server {
        listen unix:/tmp/nginx-s7.sock ssl;
        server_name   test.com;

        location /t {
            content_by_lua_block {
                local ssl = require "resty.openssl.ssl"
                local sess = myassert(ssl.from_request())

                local orig_options = myassert(sess:get_options())
                ngx.say(orig_options)
                ngx.say(require("cjson").encode(myassert(sess:get_options(true))))

                myassert(sess:set_options(ssl.SSL_OP_CIPHER_SERVER_PREFERENCE))
                myassert(sess:set_options(ssl.SSL_OP_ALLOW_NO_DHE_KEX, ssl.SSL_OP_NO_QUERY_MTU))
                ngx.say(require("cjson").encode(myassert(sess:get_options(true))))

                myassert(sess:clear_options(ssl.SSL_OP_CIPHER_SERVER_PREFERENCE))
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
    }
--- config
    location /t {
        proxy_pass https://unix:/tmp/nginx-s7.sock:;
        proxy_ssl_server_name on;
        proxy_ssl_name test.com;
        # valgrind be happy
        proxy_ssl_session_reuse off;
    }
--- request
    GET /t
--- response_body_like
\d+
\[".+"\]
.+SSL_OP_ALLOW_NO_DHE_KEX.+SSL_OP_CIPHER_SERVER_PREFERENCE.+SSL_OP_NO_QUERY_MTU.+
ok

--- no_error_log
[error]
[emerg]

=== TEST 8: SSL (server) set_protocols [skipped; need clienthello_by]
--- http_config
    server {
        listen unix:/tmp/nginx-s8.sock ssl;
        server_name   test.com;
        ssl_protocols TLSv1.3;

        ssl_certificate_by_lua_block {
            local ssl = require "resty.openssl.ssl"
            local sess = myassert(ssl.from_request())

            myassert(sess:set_protocols("TLSv1.2"))
        }

        location /t {
            content_by_lua_block {
                local ssl = require "resty.openssl.ssl"
                local sess = myassert(ssl.from_request())

                ngx.say("ok")
            }
        }
    }
--- config
    location /t {
        proxy_pass https://unix:/tmp/nginx-s8.sock:;
        proxy_ssl_server_name on;
        proxy_ssl_name test.com;
        proxy_ssl_protocols TLSv1.2;
        # valgrind be happy
        proxy_ssl_session_reuse off;
    }
--- request
    GET /t
--- response_body_like
ok

--- no_error_log
[error]
[emerg]
--- skip_nginx
2: < 9.9.9
