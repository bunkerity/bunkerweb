# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

workers(2);
master_on();

repeat_each(1);

plan tests => repeat_each() * (blocks() * 2);

check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: ngx.worker.count
--- http_config
    init_worker_by_lua_block {
        ngx.timer.at(0, function()
            local ngx_pipe = require "ngx.pipe"

            local function check_error(...)
                local data, err = pcall(...)
                if not data then
                    ngx.log(ngx.ERR, err)
                end
            end

            check_error(ngx_pipe.spawn, {"ls"})
        end)
    }
--- config
    listen $TEST_NGINX_RAND_PORT_1 reuseport;
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.01) -- ensure timer is fired
            ngx.say("ok")
        }
    }
--- request
GET /t
--- no_error_log
failed (9: Bad file descriptor)
