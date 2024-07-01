use Test::Nginx::Socket::Lua 'no_plan';


#$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';
#$ENV{TEST_COVERAGE} ||= 0;

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

our $MTLSCA = read_file("t/cert/mtls_ca.crt");
our $MTLSClient = read_file("t/cert/mtls_client.crt");
our $MTLSClientKey = read_file("t/cert/mtls_client.key");
our $TestCert = read_file("t/cert/test.crt");
our $TestKey = read_file("t/cert/test.key");

our $HtmlDir = html_dir;

use Cwd qw(cwd);
my $pwd = cwd();

our $mtls_http_config = <<"_EOC_";
    lua_package_path "$pwd/lib/?.lua;/usr/local/share/lua/5.1/?.lua;;";
server {
    listen unix:$::HtmlDir/mtls.sock ssl;

    ssl_certificate        $::HtmlDir/test.crt;
    ssl_certificate_key    $::HtmlDir/test.key;
    ssl_client_certificate $::HtmlDir/mtls_ca.crt;
    ssl_verify_client      on;
    server_tokens          off;
    server_name            example.com;

    location / {
        echo -n "hello, \$ssl_client_s_dn";
    }
}
_EOC_

our $mtls_user_files = <<"_EOC_";
>>> mtls_ca.crt
$::MTLSCA
>>> mtls_client.key
$::MTLSClientKey
>>> mtls_client.crt
$::MTLSClient
>>> test.crt
$::TestCert
>>> test.key
$::TestKey
_EOC_

run_tests();

__DATA__

=== TEST 1: Connection fails during handshake without client cert and key
--- http_config eval: $::mtls_http_config
--- config eval
"
lua_ssl_trusted_certificate $::HtmlDir/test.crt;
location /t {
    content_by_lua_block {
        local httpc = assert(require('resty.http').new())

        local ok, err = httpc:connect {
          scheme = 'https',
          host = 'unix:$::HtmlDir/mtls.sock',
        }

        if ok and not err then
          local res, err = assert(httpc:request {
            method = 'GET',
            path = '/',
            headers = {
              ['Host'] = 'example.com',
            },
          })

          ngx.status = res.status -- expect 400
        end

        httpc:close()
    }
}
"
--- user_files eval: $::mtls_user_files
--- request
GET /t
--- error_code: 400
--- no_error_log
[error]
[warn]


=== TEST 2: Connection fails during handshake with not priv_key
--- http_config eval: $::mtls_http_config
--- config eval
"
lua_ssl_trusted_certificate $::HtmlDir/test.crt;
location /t {
    content_by_lua_block {
        local f = assert(io.open('$::HtmlDir/mtls_client.crt'))
        local cert_data = f:read('*a')
        f:close()

        local ssl = require('ngx.ssl')

        local cert = assert(ssl.parse_pem_cert(cert_data))

        local httpc = assert(require('resty.http').new())

        local ok, err = httpc:connect {
          scheme = 'https',
          host = 'unix:$::HtmlDir/mtls.sock',
          ssl_client_cert = cert,
          ssl_client_priv_key = 'foo',
        }

        if ok and not err then
          local res, err = assert(httpc:request {
            method = 'GET',
            path = '/',
            headers = {
              ['Host'] = 'example.com',
            },
          })

          ngx.say(res:read_body())

        else
          ngx.say('failed to connect: ' .. (err or ''))
        end

        httpc:close()
    }
}
"
--- user_files eval: $::mtls_user_files
--- request
GET /t
--- error_code: 200
--- no_error_log
[error]
[warn]
--- response_body
failed to connect: bad ssl_client_priv_key: cdata expected, got string
--- skip_nginx
4: < 1.21.4


=== TEST 3: Connection succeeds with client cert and key.
--- http_config eval: $::mtls_http_config
--- config eval
"
lua_ssl_trusted_certificate $::HtmlDir/test.crt;

location /t {
    content_by_lua_block {
        local f = assert(io.open('$::HtmlDir/mtls_client.crt'))
        local cert_data = f:read('*a')
        f:close()

        f = assert(io.open('$::HtmlDir/mtls_client.key'))
        local key_data = f:read('*a')
        f:close()

        local ssl = require('ngx.ssl')

        local cert = assert(ssl.parse_pem_cert(cert_data))
        local key = assert(ssl.parse_pem_priv_key(key_data))

        local httpc = assert(require('resty.http').new())

        local ok, err = httpc:connect {
          scheme = 'https',
          host = 'unix:$::HtmlDir/mtls.sock',
          ssl_client_cert = cert,
          ssl_client_priv_key = key,
        }

        if ok and not err then
          local res, err = assert(httpc:request {
            method = 'GET',
            path = '/',
            headers = {
              ['Host'] = 'example.com',
            },
          })

          ngx.say(res:read_body())
        end

        httpc:close()
    }
}
"
--- user_files eval: $::mtls_user_files
--- request
GET /t
--- no_error_log
[error]
[warn]
--- response_body
hello, CN=foo@example.com,O=OpenResty,ST=California,C=US
--- skip_nginx
4: < 1.21.4

=== TEST 4: users with different client certs should not share the same pool.
--- http_config eval: $::mtls_http_config
--- config eval
"
lua_ssl_trusted_certificate $::HtmlDir/test.crt;

location /t {
    content_by_lua_block {
        local f = assert(io.open('$::HtmlDir/mtls_client.crt'))
        local cert_data = f:read('*a')
        f:close()

        f = assert(io.open('$::HtmlDir/mtls_client.key'))
        local key_data = f:read('*a')
        f:close()

        local ssl = require('ngx.ssl')

        local cert = assert(ssl.parse_pem_cert(cert_data))
        local key = assert(ssl.parse_pem_priv_key(key_data))

        f = assert(io.open('$::HtmlDir/test.crt'))
        local invalid_cert_data = f:read('*a')
        f:close()

        f = assert(io.open('$::HtmlDir/test.key'))
        local invalid_key_data = f:read('*a')
        f:close()

        local invalid_cert = assert(ssl.parse_pem_cert(invalid_cert_data))
        local invalid_key = assert(ssl.parse_pem_priv_key(invalid_key_data))

        local httpc = assert(require('resty.http').new())

        local ok, err = httpc:connect {
          scheme = 'https',
          host = 'unix:$::HtmlDir/mtls.sock',
          ssl_client_cert = cert,
          ssl_client_priv_key = key,
        }

        if ok and not err then
          local res, err = assert(httpc:request {
            method = 'GET',
            path = '/',
            headers = {
              ['Host'] = 'example.com',
            },
          })

          ngx.say(res:read_body())
        end

        httpc:set_keepalive()

        local httpc = assert(require('resty.http').new())

        local ok, err = httpc:connect {
          scheme = 'https',
          host = 'unix:$::HtmlDir/mtls.sock',
          ssl_client_cert = invalid_cert,
          ssl_client_priv_key = invalid_key,
        }

        ngx.say(httpc:get_reused_times())
        ngx.say(ok)
        ngx.say(err)

        if ok and not err then
          local res, err = assert(httpc:request {
            method = 'GET',
            path = '/',
            headers = {
              ['Host'] = 'example.com',
            },
          })

          ngx.say(res.status)   -- expect 400
        end

        httpc:close()
    }
}
"
--- user_files eval: $::mtls_user_files
--- request
GET /t
--- no_error_log
[error]
[warn]
--- response_body
hello, CN=foo@example.com,O=OpenResty,ST=California,C=US
0
true
nil
400
--- skip_nginx
4: < 1.21.4
