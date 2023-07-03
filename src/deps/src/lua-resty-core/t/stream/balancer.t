# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 2);

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::Stream::lua_package_path";

#worker_connections(1024);
#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: set current peer (separate addr and port)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.3", 12345))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
[
'[lua] balancer_by_lua:2: hello from balancer by lua! while connecting to upstream,',
qr{connect\(\) failed .*?, upstream: "127\.0\.0\.3:12345"},
]
--- no_error_log
[warn]



=== TEST 2: set current peer & next upstream (3 tries)
--- skip_nginx: 4: < 1.7.5
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream on;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            if not ngx.ctx.tries then
                ngx.ctx.tries = 0
            end

            if ngx.ctx.tries < 2 then
                local ok, err = b.set_more_tries(1)
                if not ok then
                    return error("failed to set more tries: ", err)
                elseif err then
                    ngx.log(ngx.WARN, "set more tries: ", err)
                end
            end
            ngx.ctx.tries = ngx.ctx.tries + 1
            assert(b.set_current_peer("127.0.0.3", 12345))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- grep_error_log eval: qr{connect\(\) failed .*, upstream: ".*?"}
--- grep_error_log_out eval
qr#^(?:connect\(\) failed .*?, upstream: "127.0.0.3:12345"\n){3}$#
--- no_error_log
[warn]



=== TEST 3: set current peer & next upstream (no retries)
--- skip_nginx: 4: < 1.7.5
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream on;

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            if not ngx.ctx.tries then
                ngx.ctx.tries = 0
            end

            ngx.ctx.tries = ngx.ctx.tries + 1
            assert(b.set_current_peer("127.0.0.3", 12345))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- grep_error_log eval: qr{connect\(\) failed .*, upstream: ".*?"}
--- grep_error_log_out eval
qr#^(?:connect\(\) failed .*?, upstream: "127.0.0.3:12345"\n){1}$#
--- no_error_log
[warn]



=== TEST 4: set current peer & next upstream (3 tries exceeding the limit)
--- skip_nginx: 4: < 1.7.5
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream on;
    proxy_next_upstream_tries 2;

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"

            if not ngx.ctx.tries then
                ngx.ctx.tries = 0
            end

            if ngx.ctx.tries < 2 then
                local ok, err = b.set_more_tries(1)
                if not ok then
                    return error("failed to set more tries: ", err)
                elseif err then
                    ngx.log(ngx.WARN, "set more tries: ", err)
                end
            end
            ngx.ctx.tries = ngx.ctx.tries + 1
            assert(b.set_current_peer("127.0.0.3", 12345))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- grep_error_log eval: qr{connect\(\) failed .*, upstream: ".*?"}
--- grep_error_log_out eval
qr#^(?:connect\(\) failed .*?, upstream: "127.0.0.3:12345"\n){2}$#
--- error_log
set more tries: reduced tries due to limit



=== TEST 5: get last peer failure status (connect failed)
--- skip_nginx: 4: < 1.7.5
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream on;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local state, status = b.get_last_failure()
            print("last peer failure: ", state, " ", status)

            if not ngx.ctx.tries then
                ngx.ctx.tries = 0
            end

            if ngx.ctx.tries < 2 then
                local ok, err = b.set_more_tries(1)
                if not ok then
                    return error("failed to set more tries: ", err)
                elseif err then
                    ngx.log(ngx.WARN, "set more tries: ", err)
                end
            end
            ngx.ctx.tries = ngx.ctx.tries + 1
            assert(b.set_current_peer("127.0.0.3", 12345))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- grep_error_log eval: qr{last peer failure: \S+ \S+}
--- grep_error_log_out
last peer failure: nil nil
last peer failure: failed 0
last peer failure: failed 0

--- no_error_log
[warn]



=== TEST 6: set current peer (port embedded in addr)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.3:12345"))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
[
'[lua] balancer_by_lua:2: hello from balancer by lua! while connecting to upstream,',
qr{connect\(\) failed .*?, upstream: "127\.0\.0\.3:12345"},
]
--- no_error_log
[warn]
