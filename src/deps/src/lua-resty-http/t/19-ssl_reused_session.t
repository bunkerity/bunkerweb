use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(abs_path realpath);
use File::Basename;

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';
$ENV{TEST_NGINX_CERT_DIR} ||= dirname(realpath(abs_path(__FILE__)));
$ENV{TEST_COVERAGE} ||= 0;

my $realpath = realpath();

our $HttpConfig = qq{
    lua_package_path "$realpath/lib/?.lua;/usr/local/share/lua/5.1/?.lua;;";

    init_by_lua_block {
        if $ENV{TEST_COVERAGE} == 1 then
            jit.off()
            require("luacov.runner").init()
        end

        TEST_SERVER_SOCK = "unix:/$ENV{TEST_NGINX_HTML_DIR}/nginx.sock"

        num_handshakes = 0
    }

    server {
        listen unix:$ENV{TEST_NGINX_HTML_DIR}/nginx.sock ssl;
        server_name example.com;
        ssl_certificate $ENV{TEST_NGINX_CERT_DIR}/cert/test.crt;
        ssl_certificate_key $ENV{TEST_NGINX_CERT_DIR}/cert/test.key;
        ssl_session_tickets off;

        server_tokens off;
    }
};

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: connect returns session userdata
--- http_config eval: $::HttpConfig
--- config
    server_tokens off;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;

    location /t {
        content_by_lua_block {
            local httpc = assert(require("resty.http").new())
            local ok, err, session = assert(httpc:connect {
                scheme = "https",
                host = TEST_SERVER_SOCK,
            })

            assert(type(session) == "userdata" or type(session) == "cdata", "expected session to be userdata or cdata")
            assert(httpc:close())
        }
    }

--- request
GET /t
--- no_error_log
[error]
[alert]


=== TEST 2: ssl_reused_session false does not return session userdata
--- http_config eval: $::HttpConfig
--- config
    server_tokens off;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;

    location /t {
        content_by_lua_block {
            local httpc = assert(require("resty.http").new())
            local ok, err, session = assert(httpc:connect {
                scheme = "https",
                host = TEST_SERVER_SOCK,
                ssl_reused_session = false,
            })

            assert(type(session) == "boolean", "expected session to be a boolean")
            assert(session == true, "expected session to be true")
            assert(httpc:close())
        }
    }

--- request
GET /t
--- no_error_log
[error]
[alert]


=== TEST 3: ssl_reused_session accepts userdata
--- http_config eval: $::HttpConfig
--- config
    server_tokens off;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;

    location /t {
        content_by_lua_block {
            local httpc = assert(require("resty.http").new())
            local ok, err, session = assert(httpc:connect {
                scheme = "https",
                host = TEST_SERVER_SOCK,
            })

            assert(type(session) == "userdata" or type(session) == "cdata", "expected session to be userdata or cdata")

            local httpc2 = assert(require("resty.http").new())
            local ok, err, session2 = assert(httpc2:connect {
                scheme = "https",
                host = TEST_SERVER_SOCK,
                ssl_reused_session = session,
            })

            assert(type(session2) == "userdata" or type(session2) == "cdata", "expected session2 to be userdata or cdata")

            assert(httpc:close())
            assert(httpc2:close())
        }
    }

--- request
GET /t
--- no_error_log
[error]
[alert]
