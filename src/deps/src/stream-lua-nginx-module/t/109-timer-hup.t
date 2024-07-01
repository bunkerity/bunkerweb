# vim:set ft= ts=4 sw=4 et fdm=marker:

our $SkipReason;

BEGIN {
    if ($ENV{TEST_NGINX_CHECK_LEAK}) {
        $SkipReason = "unavailable for the hup tests";

    } else {
        $ENV{TEST_NGINX_USE_HUP} = 1;
        undef $ENV{TEST_NGINX_USE_STAP};
    }
}

use Test::Nginx::Socket::Lua::Stream $SkipReason ? (skip_all => $SkipReason) : ();

use t::StapThread;

our $GCScript = $t::StapThread::GCScript;
our $StapScript = $t::StapThread::StapScript;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * 73;

#no_diff();
no_long_string();

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_HTML_DIR} = $HtmlDir;

worker_connections(1024);
run_tests();

__DATA__

=== TEST 1: single timer
--- stream_server_config
    content_by_lua_block {
        local f, err = io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        local i = 0
        local function f(premature)
            i = i + 1
            print("timer prematurely expired: ", premature)
            print("in callback: hello, ", i)
        end
        local ok, err = ngx.timer.at(3, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        os.execute("kill -HUP " .. pid)
    }

--- config
--- stream_response
registered timer

--- wait: 0.3
--- no_error_log
[error]
[alert]
[crit]
in callback: hello, 2
timer prematurely expired: false

--- error_log
lua abort pending timers
lua ngx.timer expired
stream lua close fake stream connection
in callback: hello, 1
timer prematurely expired: true



=== TEST 2: multiple timers
--- stream_server_config
    content_by_lua_block {
        local f, err = io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        local i = 0
        local function f(premature)
            i = i + 1
            print("timer prematurely expired: ", premature)
            print("in callback: hello, ", i, "!")
        end
        for i = 1, 10 do
            local ok, err = ngx.timer.at(3, f)
            if not ok then
                ngx.say("failed to set timer: ", err)
                return
            end
        end
        ngx.say("registered timers")
        os.execute("kill -HUP " .. pid)
    }

--- config
--- stream_response
registered timers

--- wait: 0.3
--- no_error_log
[error]
[alert]
[crit]
in callback: hello, 11!
timer prematurely expired: false

--- error_log
lua abort pending timers
lua ngx.timer expired
stream lua close fake stream connection
in callback: hello, 1!
in callback: hello, 2!
in callback: hello, 3!
in callback: hello, 4!
in callback: hello, 5!
in callback: hello, 6!
in callback: hello, 7!
in callback: hello, 8!
in callback: hello, 9!
in callback: hello, 10!
timer prematurely expired: true



=== TEST 3: trying to add new timer after HUP reload
--- stream_server_config
    content_by_lua_block {
        local f, err = io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        local function f(premature)
            print("timer prematurely expired: ", premature)
            local ok, err = ngx.timer.at(3, f)
            if not ok then
                print("failed to register a new timer after reload: ", err)
            else
                print("registered a new timer after reload")
            end
        end
        local ok, err = ngx.timer.at(3, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        os.execute("kill -HUP " .. pid)
    }

--- config
--- stream_response
registered timer

--- wait: 0.2
--- no_error_log
[error]
[alert]
[crit]
in callback: hello, 2
timer prematurely expired: false

--- error_log
lua abort pending timers
lua ngx.timer expired
stream lua close fake stream connection
timer prematurely expired: true
failed to register a new timer after reload: process exiting, context: ngx.timer



=== TEST 4: trying to add new timer after HUP reload
--- stream_server_config
    content_by_lua_block {
        local f, err = io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        local function g(premature)
            print("g: timer prematurely expired: ", premature)
            print("g: exiting=", ngx.worker.exiting())
        end

        local function f(premature)
            print("f: timer prematurely expired: ", premature)
            print("f: exiting=", ngx.worker.exiting())
            local ok, err = ngx.timer.at(0, g)
            if not ok then
                print("f: failed to register a new timer after reload: ", err)
            else
                print("f: registered a new timer after reload")
            end
        end
        local ok, err = ngx.timer.at(3, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        os.execute("kill -HUP " .. pid)
    }

--- config
--- stream_response
registered timer

--- wait: 0.2
--- no_error_log
[error]
[alert]
[crit]
in callback: hello, 2
failed to register a new timer after reload

--- error_log
lua abort pending timers
lua ngx.timer expired
stream lua close fake stream connection
f: timer prematurely expired: true
f: registered a new timer after reload
f: exiting=true
g: timer prematurely expired: false
g: exiting=true



=== TEST 5: HUP reload should abort pending timers
--- stream_server_config
    content_by_lua_block {
        local f, err = io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        local function f(premature)
            print("f: timer prematurely expired: ", premature)
            print("f: exiting=", ngx.worker.exiting())
        end

        for i = 1, 100 do
            local ok, err = ngx.timer.at(3 + i, f)
            if not ok then
                ngx.say("failed to set timer: ", err)
                return
            end
        end
        ngx.say("ok")
        os.execute("kill -HUP " .. pid)
    }

--- config
--- stream_response
ok

--- wait: 0.5
--- no_error_log
[error]
[alert]
[crit]
in callback: hello, 2
failed to register a new timer after reload

--- grep_error_log eval: qr/lua found \d+ pending timers/
--- grep_error_log_out
lua found 100 pending timers



=== TEST 6: HUP reload should abort pending timers (coroutine + cosocket)
TODO
--- SKIP
--- http_config
    #lua_shared_dict test_dict 1m;

    server {
        listen $TEST_NGINX_RAND_PORT_1;
        location = /foo {
            echo 'foo';
        }
    }

--- stream_server_config
    content_by_lua_block {
        local stream_req = {"GET /foo HTTP/1.1", "Host: localhost:1234", "", ""}
        stream_req = table.concat(stream_req, "\r\n")

        -- Connect the socket
        local sock = ngx.socket.tcp()
        local ok,err = sock:connect("127.0.0.1", $TEST_NGINX_RAND_PORT_1)
        if not ok then
            ngx.log(ngx.ERR, err)
        end

        -- Send the request
        local ok,err = sock:send(stream_req)

        -- Get Headers
        repeat
            local line, err = sock:receive("*l")
        until not line or string.find(line, "^%s*$")

        function foo()
            repeat
                -- Get and read chunk
                local line, err = sock:receive("*l")
                local len = tonumber(line)
                if len > 0 then
                    local chunk, err = sock:receive(len)
                    coroutine.yield(chunk)
                    sock:receive(2)
                else
                    -- Read last newline
                    sock:receive(2)
                end
            until len == 0
        end

        co = coroutine.create(foo)
        repeat
            local chunk = select(2,coroutine.resume(co))
        until chunk == nil

        -- Breaks the timer
        sock:setkeepalive()
        ngx.say("ok")

    log_by_lua_block {
        local background_thread
        background_thread = function(premature)
            ngx.log(ngx.DEBUG, premature)
            if premature then
                ngx.shared["test_dict"]:delete("background_flag")
                return
            end
            local ok, err = ngx.timer.at(1, background_thread)

            local f, err = io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r")
            if not f then
                ngx.say("failed to open nginx.pid: ", err)
                return
            end
            local pid = f:read()
            -- ngx.say("master pid: [", pid, "]")
            f:close()

            os.execute("kill -HUP " .. pid)
        end
        local dict = ngx.shared["test_dict"]

        if dict:get("background_flag") == nil then
            local ok, err = ngx.timer.at(0, background_thread)
            if ok then
                dict:set("test_dict", 1)
            end
        end
    }

--- config
    location = /foo {--- stream_response
ok

--- wait: 0.3
--- no_error_log
[error]
[alert]
[crit]
in callback: hello, 2
failed to register a new timer after reload

--- grep_error_log eval: qr/lua found \d+ pending timers/
--- grep_error_log_out
lua found 1 pending timers



=== TEST 7: HUP reload should abort pending timers (fuzz test)
--- stream_config
    lua_max_pending_timers 8192;

--- stream_server_config
    content_by_lua_block {
        local job = function(premature, kill)
            if premature then
                return
            end

            if kill then
                local f, err = assert(io.open("$TEST_NGINX_SERVER_ROOT/logs/nginx.pid", "r"))
                local pid = f:read()
                -- ngx.say("master pid: [", pid, "]")
                f:close()

                os.execute("kill -HUP " .. pid)
            end
        end

        math.randomseed(ngx.time())
        local rand = math.random
        local newtimer = ngx.timer.at
        for i = 1, 8191 do
            local delay = rand(4096)
            local ok, err = newtimer(delay, job, false)
            if not ok then
                ngx.say("failed to create timer at ", delay, ": ", err)
                return
            end
        end
        local ok, err = newtimer(0, job, true)
        if not ok then
            ngx.say("failed to create the killer timer: ", err)
            return
        end
        ngx.say("ok")
    }

--- config
--- stream_response
ok

--- wait: 0.3
--- no_error_log
[error]
[alert]

--- grep_error_log eval: qr/stream lua found \d+ pending timers/
--- grep_error_log_out
stream lua found 8191 pending timers
--- timeout: 20
