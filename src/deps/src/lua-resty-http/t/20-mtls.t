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
--- SKIP
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
        end

        httpc:close()
    }
}
"
--- user_files eval: $::mtls_user_files
--- request
GET /t
--- error_code: 200
--- error_log
could not set client certificate: bad client pkey type
--- response_body_unlike: hello, CN=foo@example.com,O=OpenResty,ST=California,C=US


=== TEST 3: Connection succeeds with client cert and key. SKIP'd for CI until feature is merged.
--- SKIP
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

