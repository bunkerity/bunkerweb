# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(1);

plan tests => repeat_each() * (blocks() * 4 + 1);

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';

sub read_file {
    my $infile = shift;
    open my $in, $infile
        or die "cannot open $infile for reading: $!";
    my $cert = do { local $/; <$in> };
    close $in;
    $cert;
}

our $DSTRootCertificate = read_file("t/cert/root-ca.crt");
our $ServerRoot = server_root();

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: set a global lua var
--- stream_config
    init_worker_by_lua_block {
        foo = ngx.md5("hello world")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("foo = ", foo)
    }
--- stream_response
foo = 5eb63bbbe01eeed093cb22bb8f5acdc3
--- no_error_log
[error]



=== TEST 2: no ngx.say()
--- stream_config
    init_worker_by_lua_block {
        ngx.say("hello")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("foo = ", foo)
    }
--- stream_response
foo = nil
--- error_log
API disabled in the context of init_worker_by_lua*



=== TEST 3: timer.at
--- stream_config
    init_worker_by_lua_block {
        _G.my_counter = 0
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end
        local function handler(premature)
            warn("timer expired (premature: ", premature, "; counter: ",
                 _G.my_counter, ")")
            _G.my_counter = _G.my_counter + 1
        end
        local ok, err = ngx.timer.at(0, handler)
        if not ok then
            ngx.log(ngx.ERR, "failed to create timer: ", err)
        end
        warn("created timer: ", ok)
    }
--- stream_server_config
    content_by_lua_block {
        -- ngx.sleep(0.001)
        ngx.say("my_counter = ", _G.my_counter)
        _G.my_counter = _G.my_counter + 1
    }
--- stream_response
my_counter = 1
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): created timer: 1
warn(): timer expired (premature: false; counter: 0)

--- no_error_log
[error]



=== TEST 4: timer.at + cosocket
--- stream_config
    init_worker_by_lua_block {
        _G.done = false
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end
        local function error(...)
            ngx.log(ngx.ERR, ...)
        end
        local function handler(premature)
            warn("timer expired (premature: ", premature, ")")

            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
            if not ok then
                error("failed to connect: ", err)
                _G.done = true
                return
            end

            local req = "flush_all\r\n"

            local bytes, err = sock:send(req)
            if not bytes then
                error("failed to send request: ", err)
                _G.done = true
                return
            end

            warn("request sent: ", bytes)

            local line, err, part = sock:receive()
            if line then
                warn("received: ", line)
            else
                error("failed to receive a line: ", err, " [", part, "]")
            end
            _G.done = true
        end

        local ok, err = ngx.timer.at(0, handler)
        if not ok then
            error("failed to create timer: ", err)
        end
        warn("created timer: ", ok)
    }
--- stream_server_config
    content_by_lua_block {
        local waited = 0
        local sleep = ngx.sleep
        while not _G.done do
            local delay = 0.001
            sleep(delay)
            waited = waited + delay
            if waited > 1 then
                ngx.say("timed out")
                return
            end
        end
        ngx.say("ok")
    }
--- stream_response
ok
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): created timer: 1
warn(): timer expired (premature: false)
warn(): request sent: 11
warn(): received: OK

--- log_level: debug
--- error_log
lua tcp socket connect timeout: 60000
lua tcp socket send timeout: 60000
lua tcp socket read timeout: 60000
--- no_error_log
[error]



=== TEST 5: init_worker_by_lua_file (simple global var)
--- stream_config
    init_worker_by_lua_file html/foo.lua;
--- stream_server_config
    content_by_lua_block {
        ngx.say("foo = ", foo)
    }
--- user_files
>>> foo.lua
foo = ngx.md5("hello world")
--- stream_response
foo = 5eb63bbbe01eeed093cb22bb8f5acdc3
--- no_error_log
[error]



=== TEST 6: timer.at + cosocket (by_lua_file)
--- main_config
env TEST_NGINX_MEMCACHED_PORT;
--- stream_config
    init_worker_by_lua_file html/foo.lua;
--- user_files
>>> foo.lua
_G.done = false
local function warn(...)
    ngx.log(ngx.WARN, ...)
end
local function error(...)
    ngx.log(ngx.ERR, ...)
end
local function handler(premature)
    warn("timer expired (premature: ", premature, ")")

    local sock = ngx.socket.tcp()
    local ok, err = sock:connect("127.0.0.1",
                                 os.getenv("TEST_NGINX_MEMCACHED_PORT"))
    if not ok then
        error("failed to connect: ", err)
        _G.done = true
        return
    end

    local req = "flush_all\r\n"

    local bytes, err = sock:send(req)
    if not bytes then
        error("failed to send request: ", err)
        _G.done = true
        return
    end

    warn("request sent: ", bytes)

    local line, err, part = sock:receive()
    if line then
        warn("received: ", line)
    else
        error("failed to receive a line: ", err, " [", part, "]")
    end
    _G.done = true
end

local ok, err = ngx.timer.at(0, handler)
if not ok then
    error("failed to create timer: ", err)
end
warn("created timer: ", ok)

--- stream_server_config
    content_by_lua_block {
        local waited = 0
        local sleep = ngx.sleep
        while not _G.done do
            local delay = 0.001
            sleep(delay)
            waited = waited + delay
            if waited > 1 then
                ngx.say("timed out")
                return
            end
        end
        ngx.say("ok")
    }
--- stream_response
ok
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): created timer: 1
warn(): timer expired (premature: false)
warn(): request sent: 11
warn(): received: OK

--- log_level: debug
--- error_log
lua tcp socket connect timeout: 60000
lua tcp socket send timeout: 60000
lua tcp socket read timeout: 60000
--- no_error_log
[error]



=== TEST 7: ngx.ctx
--- stream_config
    init_worker_by_lua_block {
        ngx.ctx.foo = "hello world"
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end
        warn("foo = ", ngx.ctx.foo)
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): foo = hello world
--- no_error_log
[error]



=== TEST 8: print
--- stream_config
    init_worker_by_lua_block {
        print("md5 = ", ngx.md5("hello world"))
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]
--- error_log
md5 = 5eb63bbbe01eeed093cb22bb8f5acdc3



=== TEST 9: unescape_uri
--- stream_config
    init_worker_by_lua_block {
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end

        warn(ngx.unescape_uri("hello%20world"))
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): hello world



=== TEST 10: escape_uri
--- stream_config
    init_worker_by_lua_block {
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end

        warn(ngx.escape_uri("hello world"))
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): hello%20world



=== TEST 11: ngx.re
--- stream_config
    init_worker_by_lua_block {
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end

        warn((ngx.re.sub("hello world", "world", "XXX", "jo")))
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]
--- grep_error_log eval: qr/warn\(\): [^,]*/
--- grep_error_log_out
warn(): hello XXX



=== TEST 12: ngx.time
--- stream_config
    init_worker_by_lua_block {
        local function warn(...)
            ngx.log(ngx.WARN, ...)
        end

        warn("time: ", ngx.time())
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]
--- grep_error_log eval: qr/warn\(\): .*?(?=, context)/
--- grep_error_log_out eval
qr/warn\(\): time: \d+/



=== TEST 13: cosocket with resolver
--- timeout: 10
--- stream_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;

    init_worker_by_lua_block {
        -- global
        logs = ""
        done = false
        local function say(...)
            logs = logs .. table.concat({...}) .. "\n"
        end

        local function handler()
            local sock = ngx.socket.tcp()
            local port = 80
            local ok, err = sock:connect("agentzh.org", port)
            if not ok then
                say("failed to connect: ", err)
                done = true
                return
            end

            say("connected: ", ok)

            local req = "GET / HTTP/1.0\r\nHost: agentzh.org\r\nConnection: close\r\n\r\n"
            -- req = "OK"

            local bytes, err = sock:send(req)
            if not bytes then
                say("failed to send request: ", err)
                done = true
                return
            end

            say("request sent: ", bytes)

            local line, err = sock:receive()
            if line then
                say("first line received: ", line)

            else
                say("failed to receive the first line: ", err)
            end

            line, err = sock:receive()
            if line then
                say("second line received: ", line)

            else
                say("failed to receive the second line: ", err)
            end

            done = true
        end

        local ok, err = ngx.timer.at(0, handler)
        if not ok then
            say("failed to create timer: ", err)
        else
            say("timer created")
        end
    }

--- stream_server_config
    content_by_lua_block {
        local i = 0
        while not done and i < 3000 do
            ngx.sleep(0.001)
            i = i + 1
        end
        ngx.print(logs)
    }
--- stream_response_like
timer created
connected: 1
request sent: 56
first line received: HTTP\/1\.1 200 OK
second line received: (?:Date|Server): .*?
--- no_error_log
[error]
--- timeout: 10



=== TEST 14: connection refused (tcp) - log_errors on by default
--- stream_config
    init_worker_by_lua_block {
        logs = ""
        done = false
        local function say(...)
            logs = logs .. table.concat{...} .. "\n"
        end

        local function handler()
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", 16787)
            if not ok then
                say("failed to connect: ", err)
            else
                say("connect: ", ok, " ", err)
            end
            done = true
        end

        local ok, err = ngx.timer.at(0, handler)
        if not ok then
            say("failed to create timer: ", err)
        else
            say("timer created")
        end
    }

--- stream_server_config
    content_by_lua_block {
        local i = 0
        while not done and i < 1000 do
            ngx.sleep(0.001)
            i = i + 1
        end
        ngx.print(logs)
    }

--- stream_response
timer created
failed to connect: connection refused
--- error_log eval
qr/connect\(\) failed \(\d+: Connection refused\), context: ngx\.timer$/



=== TEST 15: connection refused (tcp) - log_errors explicitly on
--- stream_config
    lua_socket_log_errors on;
    init_worker_by_lua_block {
        logs = ""
        done = false
        local function say(...)
            logs = logs .. table.concat{...} .. "\n"
        end

        local function handler()
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", 16787)
            if not ok then
                say("failed to connect: ", err)
            else
                say("connect: ", ok, " ", err)
            end
            done = true
        end

        local ok, err = ngx.timer.at(0, handler)
        if not ok then
            say("failed to create timer: ", err)
        else
            say("timer created")
        end
    }

--- stream_server_config
    content_by_lua_block {
        local i = 0
        while not done and i < 1000 do
            ngx.sleep(0.001)
            i = i + 1
        end
        ngx.print(logs)
    }

--- stream_response
timer created
failed to connect: connection refused
--- error_log eval
qr/connect\(\) failed \(\d+: Connection refused\)/



=== TEST 16: connection refused (tcp) - log_errors explicitly off
--- stream_config
    lua_socket_log_errors off;
    init_worker_by_lua_block {
        logs = ""
        done = false
        local function say(...)
            logs = logs .. table.concat{...} .. "\n"
        end

        local function handler()
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", 16787)
            if not ok then
                say("failed to connect: ", err)
            else
                say("connect: ", ok, " ", err)
            end
            done = true
        end

        local ok, err = ngx.timer.at(0, handler)
        if not ok then
            say("failed to create timer: ", err)
        else
            say("timer created")
        end
    }

--- stream_server_config
    content_by_lua_block {
        local i = 0
        while not done and i < 1000 do
            ngx.sleep(0.001)
            i = i + 1
        end
        ngx.print(logs)
    }

--- stream_response
timer created
failed to connect: connection refused
--- no_error_log eval
[
'qr/connect\(\) failed \(\d+: Connection refused\)/',
'[error]',
]



=== TEST 17: init_by_lua + proxy_temp_path which has side effects in cf->cycle->paths
--- SKIP
--- stream_config eval
qq!
    proxy_temp_path $::ServerRoot/proxy_temp;
    init_worker_by_lua_block {
        local a = 2 + 3
    }
!
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]
[alert]
[emerg]



=== TEST 18: syslog error log
--- stream_config
    #error_log syslog:server=127.0.0.1:12345 error;
    init_worker_by_lua_block {
        done = false
        os.execute("sleep 0.1")
        ngx.log(ngx.ERR, "Bad bad bad")
        done = true
    }
--- stream_server_config
    content_by_lua_block {
        while not done do
            ngx.sleep(0.001)
        end
        ngx.say("ok")
    }
--- log_level: error
--- error_log_file: syslog:server=127.0.0.1:12345
--- udp_listen: 12345
--- udp_query eval: qr/Bad bad bad/
--- udp_reply: hello
--- wait: 0.1
--- stream_response
ok
--- error_log
Bad bad bad
--- skip_nginx: 4: < 1.7.1



=== TEST 19: fake module calls ngx_stream_conf_get_module_srv_conf in its merge_srv_conf callback (GitHub issue #554)
This also affects merge_loc_conf
--- stream_config
    init_worker_by_lua_block { return }
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok')
    }
--- stream_response
ok
--- no_error_log
[error]



=== TEST 20: lua_ssl_trusted_certificate
--- stream_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    lua_ssl_trusted_certificate ../html/trusted.crt;
    lua_ssl_verify_depth 2;

    init_worker_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore:new(0)
        package.loaded.sem = sem

        local function test_ssl_verify()
            local sock = ngx.socket.tcp()
            sock:settimeout(2000)
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
                return
            end

            ngx.log(ngx.WARN, "connected: ", ok)

            local session, err = sock:sslhandshake(nil, "openresty.org", true)
            if not session then
                ngx.log(ngx.ERR, "failed to do SSL handshake: ", err)
                return
            end

            ngx.log(ngx.WARN, "ssl handshake: ", type(session))

            local ok, err = sock:close()
            ngx.log(ngx.WARN, "close: ", ok, " ", err)

            sem:post(1)
        end

        ngx.timer.at(0, test_ssl_verify)
    }

--- stream_server_config
    content_by_lua_block {
        local sem = package.loaded.sem
        local ok, err = sem:wait(3)
        if not ok then
            ngx.say("wait test_ssl_verify failed: ", err)
        end

        ngx.say('ok')
    }
--- user_files eval
">>> trusted.crt
$::DSTRootCertificate"

--- stream_response
ok
--- no_error_log
[error]
--- error_log
connected: 1
ssl handshake: userdata
close: 1 nil
