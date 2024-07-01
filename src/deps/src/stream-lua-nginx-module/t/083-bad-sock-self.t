# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

our $HtmlDir = html_dir;

#$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;

no_long_string();
#no_diff();
#log_level 'warn';

run_tests();

__DATA__

=== TEST 1: receive
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        sock.receive("l")
    }
--- stream_response
--- error_log
bad argument #1 to 'receive' (table expected, got string)



=== TEST 2: receiveuntil
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        sock.receiveuntil(32, "ab")
    }
--- stream_response
--- error_log
bad argument #1 to 'receiveuntil' (table expected, got number)



=== TEST 3: send (bad arg number)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.tcp()
        sock.send("hello")
    }
--- stream_response
--- error_log
expecting 2 arguments (including the object), but got 1



=== TEST 4: send (bad self)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.tcp()
        sock.send("hello", 32)
    }
--- stream_response
--- error_log
bad argument #1 to 'send' (table expected, got string)



=== TEST 5: getreusedtimes (bad self)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.tcp()
        sock.getreusedtimes(2)
    }
--- stream_response
--- error_log
bad argument #1 to 'getreusedtimes' (table expected, got number)



=== TEST 6: close (bad self)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.tcp()
        sock.close(2)
    }
--- stream_response
--- error_log
bad argument #1 to 'close' (table expected, got number)



=== TEST 7: setkeepalive (bad self)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.tcp()
        sock.setkeepalive(2)
    }
--- stream_response
--- error_log
bad argument #1 to 'setkeepalive' (table expected, got number)
