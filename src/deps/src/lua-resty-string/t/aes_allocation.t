# vi:ft=

use Test::Nginx::Socket::Lua;

repeat_each(200);

plan tests => repeat_each() * (3 * blocks());

our $HttpConfig = <<'_EOC_';
    lua_package_path 'lib/?.lua;;';
    lua_package_cpath 'lib/?.so;;';
_EOC_

#log_level 'warn';

run_tests();

__DATA__

=== TEST 1: AES buffer allocation test
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local aes = require "resty.aes"
            local str = require "resty.string"
            local rnd = require "resty.random"
            local aes_default = aes:new("secretsecretsecr", nil, aes.cipher(128, "ecb"))
            local data = rnd.bytes(math.random(4096, 16384))
            local encrypted = aes_default:encrypt(data)
            local decrypted = aes_default:decrypt(encrypted)
            ngx.say(decrypted == data)
        ';
    }
--- request
GET /t
--- response_body
true
--- no_error_log
[error]
