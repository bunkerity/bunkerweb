# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 7);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: ngx.say()
--- stream_server_config
    content_by_lua_block {
        local function f()
            ngx.say("hello")
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
    }

--- config
--- stap2
F(ngx_stream_lua_timer_handler) {
    println("lua timer handler")
}

--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[alert]
[crit]

--- error_log eval
[
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf:\d+\):3: API disabled in the context of ngx\.timer/,
"lua ngx.timer expired",
"stream lua close fake stream connection"
]



=== TEST 2: ngx.print()
--- stream_server_config
    content_by_lua_block {
        local function f()
            ngx.print("hello")
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
    }

--- config
--- stap2
F(ngx_stream_lua_timer_handler) {
    println("lua timer handler")
}

--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[alert]
[crit]

--- error_log eval
[
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf:\d+\):3: API disabled in the context of ngx\.timer/,
"lua ngx.timer expired",
"stream lua close fake stream connection"
]



=== TEST 3: ngx.flush()
--- stream_server_config
    content_by_lua_block {
        local function f()
            ngx.flush()
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
    }

--- config
--- stap2
F(ngx_stream_lua_timer_handler) {
    println("lua timer handler")
}

--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[alert]
[crit]

--- error_log eval
[
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf:\d+\):3: API disabled in the context of ngx\.timer/,
"lua ngx.timer expired",
"stream lua close fake stream connection"
]



=== TEST 4: ngx.on_abort
--- stream_server_config
    content_by_lua_block {
        local function f()
            ngx.on_abort(f)
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
    }

--- config
--- stap2
F(ngx_stream_lua_timer_handler) {
    println("lua timer handler")
}

--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[alert]
[crit]

--- error_log eval
[
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf:\d+\):3: API disabled in the context of ngx\.timer/,
"lua ngx.timer expired",
"stream lua close fake stream connection"
]



=== TEST 5: ngx.eof
--- stream_server_config
    content_by_lua_block {
        local function f()
            ngx.eof()
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
    }

--- config
--- stap2
F(ngx_stream_lua_timer_handler) {
    println("lua timer handler")
}

--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[alert]
[crit]

--- error_log eval
[
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf:\d+\):3: API disabled in the context of ngx\.timer/,
"lua ngx.timer expired",
"stream lua close fake stream connection"
]



=== TEST 6: ngx.req.socket
--- stream_server_config
    content_by_lua_block {
        local function f()
            local sock, err = ngx.req.socket()
            if not sock then
                ngx.log(ngx.ERR, "failed to get req sock: ", err)
            end
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
    }

--- config
--- stap2
F(ngx_stream_lua_timer_handler) {
    println("lua timer handler")
}

--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[alert]
[crit]

--- error_log eval
[
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf:\d+\):3: API disabled in the context of ngx\.timer/,
"lua ngx.timer expired",
"stream lua close fake stream connection"
]
