# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;use t::StapThread;

our $GCScript = <<_EOC_;
$t::StapThread::GCScript

F(ngx_http_lua_check_broken_connection) {
    println("lua check broken conn")
}

F(ngx_http_lua_request_cleanup) {
    println("lua req cleanup")
}
_EOC_

our $StapScript = $t::StapThread::StapScript;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 13);

$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';
$ENV{TEST_NGINX_MEMCACHED_PORT} ||= '11211';
$ENV{TEST_NGINX_REDIS_PORT} ||= '6379';

#no_shuffle();
no_long_string();
run_tests();

__DATA__

=== TEST 1: sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- timeout: 0.1
--- wait: 1.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 2: sleep + stop (log handler still gets called)
TODO
--- SKIP
--- stream_server_config
        lua_check_client_abort on;
    content_by_lua_block {
        ngx.sleep(1)
    log_by_lua_block {
        ngx.log(ngx.NOTICE, "here in log by lua")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- timeout: 0.2
--- abort
--- stream_response
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection
here in log by lua



=== TEST 3: sleep + ignore
--- stream_server_config
    lua_check_client_abort off;
    content_by_lua_block {
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
terminate 1: ok
delete thread 1
lua req cleanup

--- wait: 1
--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]



=== TEST 4: need body on + sleep + stop (log handler still gets called)
TODO
--- SKIP
--- stream_server_config
        lua_check_client_abort on;
        lua_need_request_body on;
    content_by_lua_block {
        ngx.sleep(1)
    log_by_lua_block {
        ngx.log(ngx.NOTICE, "here in log by lua")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- timeout: 0.2
--- abort
--- stream_response
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection
here in log by lua



=== TEST 5: ngx.req.socket + receive() + sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        sock:receive()
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- timeout: 0.2
--- abort
--- stream_request
hello
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 6: ngx.req.socket + receive(N) + sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        sock:receive(5)
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua check broken conn
lua req cleanup
delete thread 1

--- wait: 0.1
--- timeout: 0.2
--- abort
--- stream_request chomp
hello
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 7: ngx.req.socket + receive(n) + sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        sock:receive(2)
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out_like
^(?:lua check broken conn
terminate 1: ok
delete thread 1
lua req cleanup|lua check broken conn
lua req cleanup
delete thread 1)$

--- wait: 1
--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]



=== TEST 8: ngx.req.socket + m * receive(n) + sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        sock:receive(2)
        sock:receive(2)
        sock:receive(1)
        ngx.sleep(0.5)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua check broken conn
lua req cleanup
delete thread 1

--- wait: 0.6
--- timeout: 0.2
--- abort
--- stream_request chomp
hello
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 9: ngx.req.socket + receiveuntil + sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        local it = sock:receiveuntil("\n")
        it()
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- wait: 1
--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 10: ngx.req.socket + receiveuntil + it(n) + sleep + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        local it = sock:receiveuntil("\n")
        it(2)
        it(3)
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua check broken conn
lua req cleanup
delete thread 1

--- timeout: 0.2
--- wait: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 11: cosocket + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock, err = ngx.socket.tcp()
        if not sock then
            ngx.log(ngx.ERR, "failed to get socket: ", err)
            return
        end

        ok, err = sock:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
        if not ok then
            ngx.log(ngx.ERR, "failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("blpop nonexist 2\r\n")
        if not bytes then
            ngx.log(ngx.ERR, "failed to send query: ", err)
            return
        end

        -- ngx.log(ngx.ERR, "about to receive")

        local res, err = sock:receive()
        if not res then
            ngx.log(ngx.ERR, "failed to receive query: ", err)
            return
        end

        ngx.log(ngx.ERR, "res: ", res)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- wait: 1
--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection



=== TEST 12: ngx.req.socket + receive all + ignore
--- stream_server_config
    lua_check_client_abort off;
    content_by_lua_block {
        local sock = ngx.req.socket()
        local res, err, part = sock:receive("*a")
        if not res then
            ngx.log(ngx.NOTICE, "failed to receive: ", err, ": ", part)
            return
        end
        print("received data: ", res)
    }
--- stream_request
hello
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
terminate 1: ok
delete thread 1
lua req cleanup

--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
received data: hello



=== TEST 13: ngx.req.socket + receive all + stop
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local sock = ngx.req.socket()
        local res, err, part = sock:receive("*a")
        if not res then
            ngx.log(ngx.NOTICE, "failed to receive: ", err, ": ", part)
            return
        end
        error("bad")
    }
--- stream_request
hello
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
terminate 1: ok
delete thread 1
lua req cleanup

--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]



=== TEST 14: ngx.req.read_body + sleep + stop (log handler still gets called)
--- stream_server_config
        lua_check_client_abort on;
    content_by_lua_block {
        ngx.req.read_body()
        ngx.sleep(0.1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
lua check broken conn
lua req cleanup
delete thread 1

--- shutdown: 1
--- stream_response
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection
--- SKIP



=== TEST 15: sleep (default off)
--- stream_server_config
    content_by_lua_block {
        ngx.sleep(1)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
terminate 1: ok
delete thread 1
lua req cleanup

--- wait: 1
--- timeout: 0.2
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
[alert]



=== TEST 16: ngx.say
--- stream_server_config
    #postpone_output 1;
    content_by_lua_block {
        ngx.sleep(0.2)
        for i = 1, 2 do
            local ok, err = ngx.say("hello")
            if not ok then
                ngx.log(ngx.WARN, "say failed: ", err)
                return
            end
        end
    }
--- wait: 0.2
--- timeout: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
[alert]
--- error_log
say failed: nginx output filter error



=== TEST 17: ngx.print
--- stream_server_config
    #postpone_output 1;
    content_by_lua_block {
        ngx.sleep(0.2)
        for i = 1, 2 do
            local ok, err = ngx.print("hello")
            if not ok then
                ngx.log(ngx.WARN, "print failed: ", err)
                return
            end
        end
    }
--- wait: 0.2
--- timeout: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
[alert]
--- error_log
print failed: nginx output filter error



=== TEST 18: ngx.flush
--- stream_server_config
    #postpone_output 1;
    content_by_lua_block {
        ngx.say("hello")
        ngx.sleep(0.2)
        local ok, err = ngx.flush()
        if not ok then
            ngx.log(ngx.WARN, "flush failed: ", err)
            return
        end
        ngx.log(ngx.WARN, "flush succeeded")
    }
--- wait: 0.2
--- timeout: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
[alert]
--- error_log
flush succeeded



=== TEST 19: ngx.eof
--- stream_server_config
    #postpone_output 1;
    content_by_lua_block {
        ngx.sleep(0.2)
        local ok, err = ngx.eof()
        if not ok then
            ngx.log(ngx.WARN, "eof failed: ", err)
            return
        end
        ngx.log(ngx.WARN, "eof succeeded")
    }
--- wait: 0.2
--- timeout: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
[alert]
--- error_log
eof succeeded
