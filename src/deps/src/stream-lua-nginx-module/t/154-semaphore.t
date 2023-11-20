use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3) + 1;

log_level("debug");
no_long_string();
#no_diff();
run_tests();

__DATA__

=== TEST 1: timer + shutdown error log
--- stream_server_config
        content_by_lua_block {
            local function test(pre)

                local semaphore = require "ngx.semaphore"
                local sem = semaphore.new()

                local function sem_wait()

                    local ok, err = sem:wait(10)
                    if not ok then
                        ngx.log(ngx.ERR, "err: ", err)
                    else
                        ngx.log(ngx.info, "wait success")
                    end
                end

                while not ngx.worker.exiting() do
                    local co = ngx.thread.spawn(sem_wait)
                    ngx.thread.wait(co)
                end
            end

            local ok, err = ngx.timer.at(0, test)
            ngx.log(ngx.INFO, "hello, world")
            ngx.say("time: ", ok)
        }
--- request
GET /t
--- stream_response_like eval
time: 1
--- grep_error_log eval: qr/hello, world|semaphore gc wait queue is not empty/
--- grep_error_log_out
hello, world
--- shutdown_error_log
--- no_shutdown_error_log
semaphore gc wait queue is not empty



=== TEST 2: timer + shutdown error log (lua code cache off)
FIXME: this test case leaks memory.
--- stream_server_config
        lua_code_cache off;
        content_by_lua_block {
            local function test(pre)

                local semaphore = require "ngx.semaphore"
                local sem = semaphore.new()

                local function sem_wait()

                    local ok, err = sem:wait(10)
                    if not ok then
                        ngx.log(ngx.ERR, "err: ", err)
                    else
                        ngx.log(ngx.ERR, "wait success")
                    end
                end

                while not ngx.worker.exiting() do
                    local co = ngx.thread.spawn(sem_wait)
                    ngx.thread.wait(co)
                end
            end

            local ok, err = ngx.timer.at(0, test)
            ngx.log(ngx.ERR, "hello, world")
            ngx.say("time: ", ok)
        }
--- request
GET /test
--- stream_response_like eval
time: 1
--- grep_error_log eval: qr/hello, world|semaphore gc wait queue is not empty/
--- grep_error_log_out
hello, world
--- shutdown_error_log
--- no_shutdown_error_log
semaphore gc wait queue is not empty
--- SKIP



=== TEST 3: exit before post_handler was called
If gc is called before the ngx_http_lua_sema_handler and free the sema memory
ngx_http_lua_sema_handler would use the freed memory.
--- stream_server_config
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            local sem = semaphore.new()

            local function sem_wait()
                ngx.log(ngx.INFO, "ngx.sem wait start")
                local ok, err = sem:wait(10)
                if not ok then
                    ngx.log(ngx.ERR, "ngx.sem wait err: ", err)
                else
                    ngx.log(ngx.INFO, "ngx.sem wait success")
                end
            end
            local co = ngx.thread.spawn(sem_wait)
            ngx.log(ngx.INFO, "ngx.sem post start")
            sem:post()
            ngx.log(ngx.INFO, "ngx.sem post end")
            ngx.say("hello")
            ngx.exit(200)
            ngx.say("not reach here")
        }
--- request
GET /t
--- stream_response_like
hello
--- grep_error_log eval: qr/(ngx.sem .*?,|close stream connection|semaphore handler: wait queue: empty, resource count: 1)/
--- grep_error_log_out
ngx.sem wait start,
ngx.sem post start,
ngx.sem post end,
close stream connection
semaphore handler: wait queue: empty, resource count: 1
