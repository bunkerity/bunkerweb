# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 6);

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::lua_package_path";

#worker_connections(1024);
#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: set current peer (separate addr and port)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.3", 12345))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- error_log eval
[
'[lua] balancer_by_lua(nginx.conf:29):2: hello from balancer by lua! while connecting to upstream,',
qr{connect\(\) failed .*?, upstream: "http://127\.0\.0\.3:12345/t"},
]
--- no_error_log
[warn]



=== TEST 2: set current peer & next upstream (3 tries)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1;
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
--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- grep_error_log eval: qr{connect\(\) failed .*, upstream: "http://.*?"}
--- grep_error_log_out eval
qr#^(?:connect\(\) failed .*?, upstream: "http://127.0.0.3:12345/t"\n){3}$#
--- no_error_log
[warn]



=== TEST 3: set current peer & next upstream (no retries)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;

    upstream backend {
        server 0.0.0.1;
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
--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- grep_error_log eval: qr{connect\(\) failed .*, upstream: "http://.*?"}
--- grep_error_log_out eval
qr#^(?:connect\(\) failed .*?, upstream: "http://127.0.0.3:12345/t"\n){1}$#
--- no_error_log
[warn]



=== TEST 4: set current peer & next upstream (3 tries exceeding the limit)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
    proxy_next_upstream_tries 2;

    upstream backend {
        server 0.0.0.1;
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
--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- grep_error_log eval: qr{connect\(\) failed .*, upstream: "http://.*?"}
--- grep_error_log_out eval
qr#^(?:connect\(\) failed .*?, upstream: "http://127.0.0.3:12345/t"\n){2}$#
--- error_log
set more tries: reduced tries due to limit



=== TEST 5: get last peer failure status (404)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1;
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
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }

    location = /back {
        return 404;
    }
--- request
    GET /t
--- response_body_like: 404 Not Found
--- error_code: 404
--- grep_error_log eval: qr{last peer failure: \S+ \S+}
--- grep_error_log_out
last peer failure: nil nil
last peer failure: next 404
last peer failure: next 404

--- no_error_log
[warn]



=== TEST 6: get last peer failure status (500)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1;
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
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }

    location = /back {
        return 500;
    }
--- request
    GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- grep_error_log eval: qr{last peer failure: \S+ \S+}
--- grep_error_log_out
last peer failure: nil nil
last peer failure: failed 500
last peer failure: failed 500

--- no_error_log
[warn]



=== TEST 7: get last peer failure status (503)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1;
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
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }

    location = /back {
        return 503;
    }
--- request
    GET /t
--- response_body_like: 503 Service Temporarily Unavailable
--- error_code: 503
--- grep_error_log eval: qr{last peer failure: \S+ \S+}
--- grep_error_log_out eval
qr{\Alast peer failure: nil nil
last peer failure: failed 50[23]
last peer failure: failed 50[23]
\z}

--- no_error_log
[warn]



=== TEST 8: get last peer failure status (connect failed)
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
    proxy_next_upstream_tries 10;

    upstream backend {
        server 0.0.0.1;
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
--- config
    location = /t {
        proxy_pass http://backend/back;
    }

    location = /back {
        return 404;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- grep_error_log eval: qr{last peer failure: \S+ \S+}
--- grep_error_log_out
last peer failure: nil nil
last peer failure: failed 502
last peer failure: failed 502

--- no_error_log
[warn]



=== TEST 9: set current peer (port embedded in addr)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.3:12345"))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- error_log eval
[
'[lua] balancer_by_lua(nginx.conf:29):2: hello from balancer by lua! while connecting to upstream,',
qr{connect\(\) failed .*?, upstream: "http://127\.0\.0\.3:12345/t"},
]
--- no_error_log
[warn]



=== TEST 10: keepalive before balancer
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        keepalive 10;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.3:12345"))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
    GET /t
--- response_body_like: 502 Bad Gateway
--- grep_error_log eval: qr/load balancing method redefined in/
--- grep_error_log_out eval
[
"load balancing method redefined in
",
"",
]
--- error_code: 502
--- error_log eval
[
'[lua] balancer_by_lua(nginx.conf:30):2: hello from balancer by lua! while connecting to upstream,',
qr{connect\(\) failed .*?, upstream: "http://127\.0\.0\.3:12345/t"},
]
--- no_error_log
[crit]



=== TEST 11: keepalive after balancer
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
        keepalive 1;
    }
--- config
    location = /t {
        content_by_lua_block {
            local res0 = ngx.location.capture("/tt")
            local res1 = ngx.location.capture("/tt")
            local res2 = ngx.location.capture("/tt")

            if res2.status == ngx.HTTP_OK then
                ngx.print(res2.body)
            end
        }
    }

    location = /tt {
        proxy_pass http://backend/back;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location = /back {
        echo "hello keepalive!";
    }
--- request
    GET /t
--- response_body
hello keepalive!
--- error_code: 200
--- grep_error_log eval: qr{\S+ keepalive peer:.*?connection}
--- grep_error_log_out eval
["free keepalive peer: saving connection
get keepalive peer: using connection
free keepalive peer: saving connection
get keepalive peer: using connection
free keepalive peer: saving connection
",
"get keepalive peer: using connection
free keepalive peer: saving connection
get keepalive peer: using connection
free keepalive peer: saving connection
get keepalive peer: using connection
free keepalive peer: saving connection
",
]
--- no_error_log
[warn]



=== TEST 12: set_current_peer called in a wrong context
--- wait: 0.2
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 127.0.0.1:$TEST_NGINX_SERVER_PORT;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
        }
    }

--- config

    location = /fake {
        echo ok;
    }

    location = /t {
        proxy_pass http://backend/fake;

        log_by_lua_block {
            local balancer = require "ngx.balancer"
            local ok, err = balancer.set_current_peer("127.0.0.1", 1234)
            if not ok then
                ngx.log(ngx.ERR, "failed to call: ", err)
                return
            end
            ngx.log(ngx.ALERT, "unexpected success")
        }
    }

--- request
GET /t
--- response_body
ok
--- error_log eval
qr/\[error\] .*? log_by_lua.*? failed to call: API disabled in the current context/
--- no_error_log
[alert]



=== TEST 13: get_last_failure called in a wrong context
--- wait: 0.2
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 127.0.0.1:$TEST_NGINX_SERVER_PORT;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
        }
    }

--- config

    location = /fake {
        echo ok;
    }

    location = /t {
        proxy_pass http://backend/fake;

        log_by_lua_block {
            local balancer = require "ngx.balancer"
            local state, status, err = balancer.get_last_failure()
            if not state and err then
                ngx.log(ngx.ERR, "failed to call: ", err)
                return
            end
            ngx.log(ngx.ALERT, "unexpected success")
        }
    }

--- request
GET /t
--- response_body
ok
--- error_log eval
qr/\[error\] .*? log_by_lua.*? failed to call: API disabled in the current context/
--- no_error_log
[alert]



=== TEST 14: set_more_tries called in a wrong context
--- wait: 0.2
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 127.0.0.1:$TEST_NGINX_SERVER_PORT;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
        }
    }

--- config

    location = /fake {
        echo ok;
    }

    location = /t {
        proxy_pass http://backend/fake;

        log_by_lua_block {
            local balancer = require "ngx.balancer"
            local ok, err = balancer.set_more_tries(1)
            if not ok then
                ngx.log(ngx.ERR, "failed to call: ", err)
                return
            end
            ngx.log(ngx.ALERT, "unexpected success")
        }
    }

--- request
GET /t
--- response_body
ok
--- error_log eval
qr/\[error\] .*? log_by_lua.*? failed to call: API disabled in the current context/
--- no_error_log
[alert]



=== TEST 15: hot loop when proxy_upstream_next error is hit and keepalive is used.
github issue openresty/lua-nginx-module#693
--- skip_nginx: 4: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            print("hello from balancer by lua!")
            assert(b.set_current_peer("127.0.0.1", $TEST_NGINX_SERVER_PORT))
        }
        keepalive 1;
    }
--- config
    location /t {
        rewrite ^/t(.*) $1 break;
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location = /back {
        return 200;
    }

    location = /main {
        echo_location /t/back;
        echo_location /t/bad;
    }

    location = /bad {
        content_by_lua_block {
            ngx.exit(444)
        }
    }
--- request
    GET /main
--- no_error_log
[alert]
--- ignore_response
--- grep_error_log eval: qr{hello from balancer by lua!}
--- grep_error_log_out
hello from balancer by lua!
hello from balancer by lua!
hello from balancer by lua!
--- error_log eval
qr/\[error] .*? upstream prematurely closed connection while reading response header from upstream/



=== TEST 16: https (keepalive)
--- skip_nginx: 5: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            print("hello from balancer by lua!")
            assert(b.set_current_peer("127.0.0.1", $TEST_NGINX_RAND_PORT_1))
        }
        keepalive 1;
    }

    server {
        listen $TEST_NGINX_RAND_PORT_1 ssl;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location = /back {
            return 200 "ok";
        }
    }
--- config
    location /t {
        proxy_pass https://backend/back;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

--- request
    GET /t
--- no_error_log
[alert]
[error]
--- response_body chomp
ok
--- grep_error_log eval: qr{hello from balancer by lua!}
--- grep_error_log_out
hello from balancer by lua!
--- no_check_leak



=== TEST 17: https (no keepalive)
--- skip_nginx: 5: < 1.7.5
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            print("hello from balancer by lua!")
            assert(b.set_current_peer("127.0.0.1", $TEST_NGINX_RAND_PORT_2))
        }
    }

    server {
        listen $TEST_NGINX_RAND_PORT_2 ssl;
        ssl_certificate ../../cert/test.crt;
        ssl_certificate_key ../../cert/test.key;

        server_tokens off;
        location = /back {
            return 200 "ok";
        }
    }
--- config
    location /t {
        proxy_pass https://backend/back;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

--- request
    GET /t
--- no_error_log
[alert]
[error]
--- response_body chomp
ok
--- grep_error_log eval: qr{hello from balancer by lua!}
--- grep_error_log_out
hello from balancer by lua!
--- no_check_leak



=== TEST 18: test ngx.var.upstream_addr after using more than one set_current_peer
--- wait: 0.2
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_next_upstream_tries 3;

    upstream backend {
        server 127.0.0.1:$TEST_NGINX_SERVER_PORT;
        balancer_by_lua_block {
            local balancer = require "ngx.balancer"
            if ngx.ctx.tries == nil then
                balancer.set_more_tries(1)
                ngx.ctx.tries = 1
                balancer.set_current_peer("127.0.0.3", 12345)
            else
                balancer.set_current_peer("127.0.0.3", 12346)
            end
        }
    }

--- config

    location = /t {
        proxy_pass http://backend;
        log_by_lua_block {
            ngx.log(ngx.INFO, "ngx.var.upstream_addr is " .. ngx.var.upstream_addr)
        }
    }

--- request
GET /t
--- response_body_like: 502 Bad Gateway
--- error_code: 502
--- error_log eval
qr/log_by_lua\(nginx.conf:\d+\):\d+: ngx.var.upstream_addr is 127.0.0.3:12345, 127.0.0.3:12346/
--- no_error_log
[alert]



=== TEST 19: recreate upstream module requests with header change
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;

        balancer_by_lua_block {
            print("here")
            local b = require "ngx.balancer"

            if ngx.ctx.balancer_run then
                assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
                ngx.var.test = "second"
                assert(b.recreate_request())

            else
                ngx.ctx.balancer_run = true
                assert(b.set_current_peer("127.0.0.3", 12345))
                assert(b.set_more_tries(1))
            end
        }
    }
--- config
    location = /t {
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504 http_403 http_404;
        proxy_next_upstream_tries 2;

        set $test "first";

        proxy_set_header X-Test $test;
        proxy_pass http://backend/upstream;
    }

    location = /upstream {
        return 200 "value is: $http_x_test";
    }
--- request
GET /t
--- response_body: value is: second
--- error_log
connect() failed (111: Connection refused) while connecting to upstream, client: 127.0.0.1
--- no_error_log
[warn]
[crit]
