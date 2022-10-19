# vi:ft=

use Test::Nginx::Socket::Lua;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

our $HttpConfig = <<'_EOC_';
    lua_package_path 'lib/?.lua;;';
    lua_package_cpath 'lib/?.so;;';
_EOC_

no_long_string();

run_tests();

__DATA__

=== TEST 1: atoi
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local str = require "resty.string"
            ngx.say(1 + str.atoi("32"))
        ';
    }
--- request
GET /t
--- response_body
33
--- no_error_log
[error]
