# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 6 - 3);

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.worker.exiting
--- config
    location = /t {
        content_by_lua_block {
            local v
            local exiting = ngx.worker.exiting
            for i = 1, 30 do
                v = exiting()
            end
            ngx.say(v)
        }
    }
--- request
GET /t
--- response_body
false
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:
 stitch



=== TEST 2: ngx.worker.pid
--- config
    location = /t {
        content_by_lua_block {
            local v
            local pid = ngx.worker.pid
            for i = 1, 30 do
                v = pid()
            end
            ngx.say(v == tonumber(ngx.var.pid))
            ngx.say(v)
        }
    }
--- request
GET /t
--- response_body_like chop
^true
\d+$
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:
 stitch



=== TEST 3: ngx.worker.id
--- config
    location = /t {
        content_by_lua_block {
            local v
            local id = ngx.worker.id
            for i = 1, 30 do
                v = id()
            end
            ngx.say("worker id: ", v)
        }
    }
--- request
GET /t
--- response_body_like chop
^worker id: [0-1]$
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:
 stitch
--- skip_nginx: 3: <=1.9.0



=== TEST 4: ngx.worker.count
--- config
    location = /t {
        content_by_lua_block {
            local v
            local count = ngx.worker.count
            for i = 1, 30 do
                v = count()
            end
            ngx.say("workers: ", v)
        }
    }
--- request
GET /t
--- response_body
workers: 1
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/
--- no_error_log
[error]
 -- NYI:
 stitch



=== TEST 5: ngx.worker.pids
--- config
    location /lua {
        content_by_lua_block {
            local pids = ngx.worker.pids()
            local pid = ngx.worker.pid()
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
    }
--- request
GET /lua
--- response_body_like
worker pid: \d+
worker pid is correct\.
--- no_error_log
[error]
