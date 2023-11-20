# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('debug'); # to ensure any log-level can be outputed

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 2);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: test log-level STDERR
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.STDERR, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 2: test log-level EMERG
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.EMERG, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[emerg\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 3: test log-level ALERT
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.ALERT, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[alert\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 4: test log-level CRIT
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.CRIT, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[crit\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 5: test log-level ERR
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.ERR, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[error\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 6: test log-level WARN
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.WARN, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[warn\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 7: test log-level NOTICE
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.NOTICE, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[notice\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 8: test log-level INFO
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.INFO, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[info\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 9: test log-level DEBUG
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        ngx.log(ngx.DEBUG, "hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[debug\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 10: regression test print()
--- stream_server_config
    content_by_lua_block {
        ngx.say("before log")
        print("hello, log", 1234, 3.14159)
        ngx.say("after log")
    }
--- stream_response
before log
after log
--- error_log eval
qr/\[notice\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):3: hello, log12343.14159/



=== TEST 11: print(nil)
--- stream_server_config
    content_by_lua_block {
        print()
        print(nil)
        print("nil: ", nil)
        ngx.say("hi");
    }
--- stream_response
hi
--- error_log eval
[
qr/\[lua\] content_by_lua\(nginx\.conf:\d+\):2: ,/,
qr/\[lua\] content_by_lua\(nginx\.conf:\d+\):3: nil,/,
qr/\[lua\] content_by_lua\(nginx\.conf:\d+\):4: nil: nil,/,
]



=== TEST 12: test booleans and nil
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.ERR, true, false, nil)
        ngx.say(32)
    }
--- stream_response
32
--- error_log eval
qr/\[error\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):2: truefalsenil/



=== TEST 13: ngx.log() big data
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.ERR, "a" .. string.rep("h", 1970) .. "b")
        ngx.say("hi")
    }
--- response_headers
--- error_log eval
[qr/ah{1970}b/]



=== TEST 14: ngx.log in Lua function calls & inlined lua
--- stream_server_config
    content_by_lua_block {
        function foo()
            bar()
        end

        function bar()
            ngx.log(ngx.ERR, "hello, log", 1234, 3.14159)
        end

        foo()
        ngx.say("done")
    }
--- stream_response
done
--- error_log eval
qr/\[error\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):7: bar\(\): hello, log12343.14159/



=== TEST 15: ngx.log in Lua function tail-calls & inlined lua
--- stream_server_config
    content_by_lua_block {
        function foo()
            return bar(5)
        end

        function bar(n)
            if n < 1 then
                ngx.log(ngx.ERR, "hello, log", 1234, 3.14159)
                return n
            end

            return bar(n - 1)
        end

        foo()
        ngx.say("done")
    }
--- stream_response
done
--- error_log eval
qr/\[error\] \S+: \S+ stream \[lua\] content_by_lua\(nginx\.conf:\d+\):8:(?: foo\(\):)? hello, log12343.14159/



=== TEST 16: ngx.log in Lua files
--- stream_server_config
    content_by_lua_file 'html/test.lua';
--- user_files
>>> test.lua
function foo()
    bar()
end

function bar()
    ngx.log(ngx.ERR, "hello, log", 1234, 3.14159)
end

foo()
ngx.say("done")

--- stream_response
done
--- error_log eval
qr/\[error\] \S+: \S+ stream \[lua\] test.lua:6: bar\(\): hello, log12343.14159/



=== TEST 17: ngx.log with bad levels (ngx.ERROR, -1)
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.ERROR, "hello lua")
        ngx.say("done")
    }
--- stream_response
--- error_log
bad log level: -1



=== TEST 18: ngx.log with bad levels (9)
--- stream_server_config
    content_by_lua_block {
        ngx.log(9, "hello lua")
        ngx.say("done")
    }
--- stream_response
--- error_log
bad log level: 9



=== TEST 19: \0 in the log message
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.WARN, "hello\0world")
        ngx.say("ok")
    }
--- stream_response
ok
--- no_error_log
[error]
--- error_log eval
"2: hello\0world"
