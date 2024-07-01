# vim:set ft= ts=4 sw=4 et:

use Test::Nginx::Socket::Lua;
use Cwd qw(cwd);

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

my $pwd = cwd();

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;;";
};

$ENV{TEST_NGINX_RESOLVER} = '8.8.8.8';

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: sha1 version
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local sha1 = require "resty.sha1"
            ngx.say(sha1._VERSION)
        ';
    }
--- request
    GET /t
--- response_body_like chop
^\d+\.\d+$
--- no_error_log
[error]



=== TEST 2: md5 version
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local md5 = require "resty.md5"
            ngx.say(md5._VERSION)
        ';
    }
--- request
    GET /t
--- response_body_like chop
^\d+\.\d+$
--- no_error_log
[error]



=== TEST 3: resty.string version
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local str = require "resty.string"
            ngx.say(str._VERSION)
        ';
    }
--- request
    GET /t
--- response_body_like chop
^\d+\.\d+$
--- no_error_log
[error]



=== TEST 4: resty.random version
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local rand = require "resty.random"
            ngx.say(rand._VERSION)
        ';
    }
--- request
    GET /t
--- response_body_like chop
^\d+\.\d+$
--- no_error_log
[error]



=== TEST 5: resty.aes version
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local aes = require "resty.aes"
            ngx.say(aes._VERSION)
        ';
    }
--- request
    GET /t
--- response_body_like chop
^\d+\.\d+$
--- no_error_log
[error]
