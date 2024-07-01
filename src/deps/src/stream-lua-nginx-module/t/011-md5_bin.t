# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
#no_long_string();
run_tests();


#md5_bin_bin is hard to test, so convert it to hex mode

__DATA__

=== TEST 1: set md5_bin hello ????xxoo
--- stream_server_config
    content_by_lua_block {
        local a = string.gsub(ngx.md5_bin("hello"), ".", function (c)
            return string.format("%02x", string.byte(c))
        end)
        ngx.say(a)
    }
--- stream_response
5d41402abc4b2a76b9719d911017c592
--- no_error_log
[error]



=== TEST 2: set md5_bin hello ????xxoo
--- stream_server_config
    content_by_lua_block { ngx.say(string.len(ngx.md5_bin("hello"))) }
--- stream_response
16
--- no_error_log
[error]



=== TEST 3: set md5_bin hello
--- stream_server_config
    content_by_lua_block {
        local s = ngx.md5_bin("hello")
        s = string.gsub(s, ".", function (c)
                return string.format("%02x", string.byte(c))
            end)
        ngx.say(s)
    }
--- stream_response
5d41402abc4b2a76b9719d911017c592
--- no_error_log
[error]



=== TEST 4: nil string to ngx.md5_bin
--- stream_server_config
    content_by_lua_block {
        local s = ngx.md5_bin(nil)
        s = string.gsub(s, ".", function (c)
                return string.format("%02x", string.byte(c))
            end)
        ngx.say(s)
    }
--- stream_response
d41d8cd98f00b204e9800998ecf8427e
--- no_error_log
[error]



=== TEST 5: null string to ngx.md5_bin
--- stream_server_config
    content_by_lua_block {
        local s = ngx.md5_bin("")
        s = string.gsub(s, ".", function (c)
                return string.format("%02x", string.byte(c))
            end)
        ngx.say(s)
    }
--- stream_response
d41d8cd98f00b204e9800998ecf8427e
--- no_error_log
[error]



=== TEST 6: md5_bin(number)
--- stream_server_config
    content_by_lua_block {
        s = ngx.md5_bin(45)
        s = string.gsub(s, ".", function (c)
                return string.format("%02x", string.byte(c))
            end)
        ngx.say(s)
    }
--- stream_response
6c8349cc7260ae62e3b1396831a8398f
--- no_error_log
[error]
