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

repeat_each(2);

plan tests => repeat_each() * (blocks() * 8);

worker_connections(1024);
no_long_string();
run_tests();

__DATA__

=== TEST 1: exiting
--- stream_server_config
    content_by_lua_block {
        local pidfile = ngx.config.prefix() .. "/logs/nginx.pid"
        local f, err = io.open(pidfile, "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        local i = 0

        local function f(premature)
            print("timer prematurely expired: ", premature)

            local sock = ngx.socket.tcp()

            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
            if not ok then
                print("failed to connect: ", err)
                return
            end

            local ok, err = sock:setkeepalive()
            if not ok then
                print("failed to setkeepalive: ", err)
                return
            end

            print("setkeepalive successfully")
        end
        local ok, err = ngx.timer.at(3, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        os.execute("kill -HUP " .. pid)
    }
--- stream_response
registered timer
--- wait: 0.3
--- no_error_log
[error]
[alert]
[crit]
--- error_log
timer prematurely expired: true
setkeepalive successfully
lua tcp socket set keepalive while process exiting, closing connection
