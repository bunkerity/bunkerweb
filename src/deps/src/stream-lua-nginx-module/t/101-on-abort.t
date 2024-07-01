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

plan tests => repeat_each() * (blocks() * 4 + 27);

$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';
$ENV{TEST_NGINX_MEMCACHED_PORT} ||= '11211';
$ENV{TEST_NGINX_REDIS_PORT} ||= '6379';

#no_shuffle();
no_long_string();
run_tests();

__DATA__

=== TEST 1: ignore the client abort event in the user callback
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.sleep(0.7)
        ngx.log(ngx.NOTICE, "main handler done")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out_like chop
^create 2 in 1
lua check broken conn
terminate 2: ok
(?:lua check broken conn
)?terminate 1: ok
delete thread 2
delete thread 1
lua req cleanup

--- timeout: 0.2
--- abort
--- wait: 0.7
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection
on abort called
main handler done



=== TEST 2: abort in the user callback
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
            ngx.exit(444)
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.sleep(0.7)
        ngx.log(ngx.NOTICE, "main handler done")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
lua check broken conn
terminate 2: ok
lua req cleanup
delete thread 2
delete thread 1

--- timeout: 0.2
--- wait: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
main handler done
--- error_log
stream client prematurely closed connection
on abort called



=== TEST 3: accessing cosocket in callback
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_REDIS_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect to redis: ", err)
                ngx.exit(499)
            end
            local bytes, err = sock:send("flushall\r\n")
            if not bytes then
                ngx.log(ngx.ERR, "failed to send query: ", err)
                ngx.exit(499)
            end

            local res, err = sock:receive()
            if not res then
                ngx.log(ngx.ERR, "failed to receive: ", err)
                ngx.exit(499)
            end
            ngx.log(ngx.NOTICE, "callback done: ", res)
            ngx.exit(499)
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.sleep(0.7)
        ngx.log(ngx.NOTICE, "main handler done")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
lua check broken conn
terminate 2: ok
lua req cleanup
delete thread 2
delete thread 1

--- timeout: 0.2
--- abort
--- wait: 0.5
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
main handler done
--- error_log
stream client prematurely closed connection
on abort called
callback done: +OK



=== TEST 4: ignore the client abort event in the user callback (no check)
--- stream_server_config
        lua_check_client_abort off;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            ngx.say("cannot set on_abort: ", err)
            return
        end

        ngx.sleep(0.7)
        ngx.log(ngx.NOTICE, "main handler done")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
terminate 1: ok
delete thread 1
lua req cleanup

--- timeout: 0.2
--- abort
--- stream_response
cannot set on_abort: lua_check_client_abort is off
--- no_error_log
stream client prematurely closed connection
on abort called
main handler done



=== TEST 5: regsiter on_abort callback but no client abortion
--- stream_server_config
        lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.say("done")
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
terminate 1: ok
delete thread 1
lua req cleanup
delete thread 2

--- stream_response
done
--- no_error_log
[error]
stream client prematurely closed connection
on abort called
main handler done



=== TEST 6: ignore the client abort event in the user callback (uthread)
--- stream_server_config
        lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.thread.spawn(function ()
            ngx.sleep(0.7)
            ngx.log(ngx.NOTICE, "main handler done")
        end)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
create 3 in 1
spawn user thread 3 in 1
terminate 1: ok
delete thread 1
lua check broken conn
terminate 2: ok
delete thread 2
terminate 3: ok
delete thread 3
lua req cleanup

--- timeout: 0.2
--- abort
--- wait: 0.7
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
--- error_log
stream client prematurely closed connection
on abort called
main handler done



=== TEST 7: abort in the user callback (uthread)
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
            ngx.exit(444)
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.thread.spawn(function ()
            ngx.sleep(0.7)
            ngx.log(ngx.NOTICE, "main handler done")
        end)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
create 3 in 1
spawn user thread 3 in 1
terminate 1: ok
delete thread 1
lua check broken conn
terminate 2: ok
lua req cleanup
delete thread 2
delete thread 3

--- timeout: 0.2
--- wait: 0.1
--- abort
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
main handler done
--- error_log
stream client prematurely closed connection
on abort called



=== TEST 8: regsiter on_abort callback but no client abortion (uthread)
--- stream_server_config
        lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.thread.spawn(function ()
            ngx.sleep(0.1)
            ngx.say("done")
        end)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
create 3 in 1
spawn user thread 3 in 1
terminate 1: ok
delete thread 1
terminate 3: ok
delete thread 3
lua req cleanup
delete thread 2

--- stream_response
done
--- no_error_log
[error]
stream client prematurely closed connection
on abort called
main handler done



=== TEST 9: regsiter on_abort callback multiple times
--- stream_server_config
        lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            ngx.say("1: cannot set on_abort: " .. err)
            return
        end

        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            ngx.say("2: cannot set on_abort: " .. err)
            return
        end

        ngx.thread.spawn(function ()
            ngx.sleep(0.1)
            ngx.say("done")
        end)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
terminate 1: ok
delete thread 1
lua req cleanup
delete thread 2

--- stream_response
2: cannot set on_abort: duplicate call

--- no_error_log
[error]



=== TEST 10: regsiter on_abort callback but no client abortion (2 uthreads and 1 pending)
--- stream_server_config
    lua_check_client_abort on;
    content_by_lua_block {
        local ok, err = ngx.on_abort(function ()
            ngx.log(ngx.NOTICE, "on abort called")
        end)

        if not ok then
            error("cannot set on_abort: " .. err)
        end

        ngx.thread.spawn(function ()
            ngx.sleep(0.1)
            ngx.say("done")
            ngx.exit(200)
        end)

        ngx.thread.spawn(function ()
            ngx.sleep(100)
        end)
    }
--- stap2 eval: $::StapScript
--- stap eval: $::GCScript
--- stap_out
create 2 in 1
create 3 in 1
spawn user thread 3 in 1
create 4 in 1
spawn user thread 4 in 1
terminate 1: ok
delete thread 1
terminate 3: ok
lua req cleanup
delete thread 2
delete thread 3
delete thread 4

--- wait: 0.5
--- stream_response
done
--- no_error_log
[error]
stream client prematurely closed connection
on abort called
main handler done
