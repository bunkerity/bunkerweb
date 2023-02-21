# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: content_by_lua + ngx.worker.exiting
--- stream_server_config
    content_by_lua_block {
        ngx.say("worker exiting: ", ngx.worker.exiting())
    }
--- stream_response
worker exiting: false
--- no_error_log
[error]



=== TEST 2: content_by_lua + ngx.worker.pid
TODO
--- SKIP
--- stream_server_config
    content_by_lua_block {
        local pid = ngx.worker.pid()
        ngx.say("worker pid: ", pid)
        if pid ~= tonumber(ngx.var.pid) then
            ngx.say("worker pid is wrong.")
        else
            ngx.say("worker pid is correct.")
        end
    }
--- stream_response_like
worker pid: \d+
worker pid is correct\.
--- no_error_log
[error]



=== TEST 3: content_by_lua + ngx.worker.pid
--- stream_server_config
    content_by_lua_block {
        local pid = ngx.worker.pid()
        ngx.say("worker pid: ", pid)
    }
--- stream_response_like
^worker pid: \d+
--- no_error_log
[error]



=== TEST 4: init_worker_by_lua + ngx.worker.pid
TODO
--- SKIP
--- stream_config
    init_worker_by_lua_block {
        my_pid = ngx.worker.pid()
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("worker pid: ", my_pid)
        if my_pid ~= tonumber(ngx.var.pid) then
            ngx.say("worker pid is wrong.")
        else
            ngx.say("worker pid is correct.")
        end
    }
--- stream_response_like
worker pid: \d+
worker pid is correct\.
--- no_error_log
[error]



=== TEST 5: init_worker_by_lua + ngx.worker.pid
--- stream_config
    init_worker_by_lua_block {
        my_pid = ngx.worker.pid()
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("worker pid: ", my_pid)
    }
--- stream_response_like
worker pid: \d+
--- no_error_log
[error]



=== TEST 6: content_by_lua + ngx.worker.pids
--- stream_server_config
    content_by_lua_block {
        local pid = ngx.worker.pid()
        local pids = ngx.worker.pids()
        ngx.say("worker pid: ", pid)
        local count = ngx.worker.count()
        if count ~= #pids then
            ngx.say("worker pids is wrong.")
        end
        for i = 1, count do
            if pids[i] == pid then
                ngx.say("worker pid is correct.")
                return
            end
        end
        ngx.say("worker pid is wrong.")
    }
--- stream_response_like
worker pid: \d+
worker pid is correct\.
--- no_error_log
[error]
