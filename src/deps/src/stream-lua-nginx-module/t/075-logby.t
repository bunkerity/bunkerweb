# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
log_level('debug');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 8);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: log_by_lua
--- stream_server_config
    content_by_lua_block {
        ngx.say('hello')
    }

    log_by_lua_block { ngx.log(ngx.ERR, "Hello from log_by_lua: ", ngx.var.protocol) }
--- stream_response
hello
--- error_log
Hello from log_by_lua: TCP



=== TEST 2: log_by_lua_file
--- stream_server_config
    content_by_lua_block {
        ngx.say('hello')
    }

    log_by_lua_file html/a.lua;
--- user_files
>>> a.lua
ngx.log(ngx.ERR, "Hello from log_by_lua: ", ngx.var.protocol)
--- stream_response
hello
--- error_log
Hello from log_by_lua: TCP



=== TEST 3: log_by_lua_file & content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.var.remote_addr) }
    log_by_lua_file html/a.lua;
--- user_files
>>> a.lua
ngx.log(ngx.ERR, "Hello from log_by_lua: ", ngx.var.status)
--- stream_response
127.0.0.1
--- error_log
Hello from log_by_lua: 200



=== TEST 4: ngx.ctx available in log_by_lua (already defined)
--- stream_server_config
    content_by_lua_block { ngx.ctx.counter = 3 ngx.say(ngx.ctx.counter) }
    log_by_lua_block { ngx.log(ngx.ERR, "ngx.ctx.counter: ", ngx.ctx.counter) }
--- stream_response
3
--- error_log
ngx.ctx.counter: 3
lua release ngx.ctx



=== TEST 5: ngx.ctx available in log_by_lua (not defined yet)
--- stream_server_config
    content_by_lua_block {
        ngx.say('hello')
    }

    log_by_lua_block {
            ngx.log(ngx.ERR, "ngx.ctx.counter: ", ngx.ctx.counter)
            ngx.ctx.counter = "hello world"
    }
--- stream_response
hello
--- error_log
ngx.ctx.counter: nil
lua release ngx.ctx



=== TEST 6: log_by_lua + shared dict
--- stream_config
    lua_shared_dict foo 100k;
--- stream_server_config
    content_by_lua_block {
        ngx.say('hello')
    }

    log_by_lua_block {
            local foo = ngx.shared.foo
            local key = ngx.var.remote_addr .. ngx.status
            local newval, err = foo:incr(key, 1)
            if not newval then
                if err == "not found" then
                    foo:add(key, 0)
                    newval, err = foo:incr(key, 1)
                    if not newval then
                        ngx.log(ngx.ERR, "failed to incr ", key, ": ", err)
                        return
                    end
                else
                    ngx.log(ngx.ERR, "failed to incr ", key, ": ", err)
                    return
                end
            end
            print(key, ": ", foo:get(key))
    }
--- stream_response
hello
--- error_log eval
qr{127.0.0.1200: [12]}
--- no_error_log
[error]



=== TEST 7: lua error (string)
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { error("Bad") }
--- stream_response
ok
--- error_log eval
qr/failed to run log_by_lua\*: log_by_lua\(nginx\.conf:\d+\):1: Bad/



=== TEST 8: lua error (nil)
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { error(nil) }
--- stream_response
ok
--- error_log
failed to run log_by_lua*: unknown reason



=== TEST 9: globals shared
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block {
            if not foo then
                foo = 1
            else
                ngx.log(ngx.INFO, "old foo: ", foo)
                foo = foo + 1
            end
    }
--- stream_response
ok
--- grep_error_log eval: qr/old foo: \d+/
--- grep_error_log_out eval
["", "old foo: 1\n"]



=== TEST 10: no ngx.print
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { ngx.print(32) return 1 }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 11: no ngx.say
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { ngx.say(32) return 1 }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 12: no ngx.flush
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { ngx.flush() }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 13: no ngx.eof
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { ngx.eof() }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 14: no ngx.exit
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { ngx.exit(0) }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 15: no ngx.req.socket()
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { return ngx.req.socket() }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 16: no ngx.socket.tcp()
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { return ngx.socket.tcp() }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 17: no ngx.socket.connect()
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block { return ngx.socket.connect("127.0.0.1", 80) }
--- stream_response
ok
--- error_log
API disabled in the context of log_by_lua*



=== TEST 18: backtrace
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_block {
            function foo()
                bar()
            end

            function bar()
                error("something bad happened")
            end

            foo()
    }
--- stream_response
ok
--- error_log
something bad happened
stack traceback:
in function 'error'
in function 'bar'
in function 'foo'



=== TEST 19: Lua file does not exist
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    log_by_lua_file html/test2.lua;
--- user_files
>>> test.lua
v = ngx.var["request_uri"]
ngx.print("request_uri: ", v, "\n")
--- stream_response
ok
--- error_log eval
qr/failed to load external Lua file ".*?test2\.lua": cannot open .*? No such file or directory/



=== TEST 20: log_by_lua runs before access logging (github issue #254)
--- stream_config
    log_format basic '$remote_addr [$time_local] '
                     '$protocol $status $bytes_sent $bytes_received '
                     '$session_time';

--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }

    access_log logs/foo.log basic;
    log_by_lua_block { print("hello") }
--- stap
F(ngx_http_log_handler) {
    println("log handler")
}
F(ngx_http_lua_log_handler) {
    println("lua log handler")
}
--- stap_out
lua log handler
log handler

--- stream_response
ok
--- no_error_log
[error]
