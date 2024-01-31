# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

#worker_connections(10140);
#workers(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 2);

no_long_string();
#no_diff();
$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::Stream::lua_package_path";
our $HttpConfig = <<_EOC_;
    lua_package_path "$t::TestCore::Stream::lua_package_path";
_EOC_

run_tests();

__DATA__

=== TEST 1: basic semaphore in uthread
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new()

        local function sem_wait()
            ngx.say("enter waiting")

            local ok, err = sem:wait(1)
            if not ok then
                ngx.say("err: ", err)
            else
                ngx.say("wait success")
            end
        end

        local co = ngx.thread.spawn(sem_wait)

        ngx.say("back in main thread")

        sem:post()

        ngx.say("still in main thread")

        ngx.sleep(0.01)

        ngx.say("main thread end")
    }
--- stream_response
enter waiting
back in main thread
still in main thread
wait success
main thread end
--- no_error_log
[error]



=== TEST 2: semaphore wait order
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new()

        local function sem_wait(id)
            ngx.say("enter waiting, id: ", id)

            local ok, err = sem:wait(1)
            if not ok then
                ngx.say("err: ", err)
            else
                ngx.say("wait success, id: ", id)
            end
        end

        local co1 = ngx.thread.spawn(sem_wait, 1)
        local co2 = ngx.thread.spawn(sem_wait, 2)

        ngx.say("back in main thread")

        sem:post(2)

        local ok, err = sem:wait(0)
        if ok then
            ngx.say("wait success in main thread")
        else
            ngx.say("wait failed in main thread: ", err) -- busy
        end

        ngx.say("still in main thread")

        local ok, err = sem:wait(0.01)
        if ok then
            ngx.say("wait success in main thread")
        else
            ngx.say("wait failed in main thread: ", err)
        end

        ngx.sleep(0.01)

        ngx.say("main thread end")
    }
--- stream_response
enter waiting, id: 1
enter waiting, id: 2
back in main thread
wait failed in main thread: timeout
still in main thread
wait success, id: 1
wait success, id: 2
wait failed in main thread: timeout
main thread end
--- no_error_log
[error]



=== TEST 3: semaphore wait time=0
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(1)

        local function wait_1s()
            ngx.say("enter 1s wait")

            local ok, err = sem:wait(1)
            if not ok then
                ngx.say("err in wait 1s: ", err)
            else
                ngx.say("wait success in 1s wait")
            end
        end

        local function wait_0()
            local ok, err = sem:wait(0)
            if not ok then
                ngx.say("err: ", err)
            else
                ngx.say("wait success")
            end
        end

        wait_0()
        wait_0()

        local co = ngx.thread.spawn(wait_1s)

        ngx.say("back in main thread")

        wait_0()

        sem:post(2)

        wait_0()

        ngx.say("still in main thread")

        ngx.sleep(0.01)

        wait_0()

        ngx.say("main thread end")
    }
--- stream_response
wait success
err: timeout
enter 1s wait
back in main thread
err: timeout
err: timeout
still in main thread
wait success in 1s wait
wait success
main thread end
--- no_error_log
[error]



=== TEST 4: semaphore.new in init_by_lua* (w/o shdict)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, err)
        else
            ngx.log(ngx.WARN, "sema created: ", tostring(sem))
        end
        sem:post(2)
        package.loaded.my_sema = sem
    }
--- stream_server_config
    content_by_lua_block {
        local sem = package.loaded.my_sema
        ngx.say("sem count: ", sem:count())
        -- sem:post(1)
        local ok, err = sem:wait(0)
        if not ok then
            ngx.say("failed to wait: ", err)
            return
        end
        ngx.say("waited successfully.")
    }
--- stream_response_like
sem count: [12]
waited successfully.
--- grep_error_log eval
qr/\[lua\] init_by_lua:\d+: sema created: table: 0x[a-f0-9]+/
--- grep_error_log_out eval
[
qr/\[lua\] init_by_lua:\d+: sema created: table: 0x[a-f0-9]+/,
"",
]



=== TEST 5: semaphore.new in init_by_lua* (with shdict)
--- stream_config
    lua_shared_dict dogs 1m;
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, err)
        else
            ngx.log(ngx.WARN, "sema created: ", tostring(sem))
        end
        sem:post(2)
        package.loaded.my_sema = sem
    }
--- stream_server_config
    content_by_lua_block {
        local sem = package.loaded.my_sema
        ngx.say("sem count: ", sem:count())
        -- sem:post(1)
        local ok, err = sem:wait(0)
        if not ok then
            ngx.say("failed to wait: ", err)
            return
        end
        ngx.say("waited successfully.")
    }
--- stream_response_like
sem count: [12]
waited successfully.
--- grep_error_log eval
qr/\[lua\] init_by_lua:\d+: sema created: table: 0x[a-f0-9]+/
--- grep_error_log_out eval
[
qr/\[lua\] init_by_lua:\d+: sema created: table: 0x[a-f0-9]+/,
"",
]



=== TEST 6: semaphore in init_worker_by_lua (wait is not allowed)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_worker_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, "sem new: ", err)
        end

        sem:post(1)

        local count = sem:count()
        ngx.log(ngx.ERR, "sem count: ", count)

        local ok, err = sem:wait(0.1)
        if not ok then
            ngx.log(ngx.ERR, "sem wait: ", err)
        end
    }
--- stream_server_config
    return "ok";
--- stream_response chop
ok
--- grep_error_log eval: qr/sem \w+: .*?,/
--- grep_error_log_out eval
[
"sem count: 1,
sem wait: API disabled in the context of init_worker_by_lua*,
",
"",
]



=== TEST 7: semaphore in init_worker_by_lua (new and post)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_worker_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, "sem new: ", err)
        end

        sem:post(2)

        local count = sem:count()
        ngx.log(ngx.WARN, "sem count: ", count)

        package.loaded.my_sema = sem
    }
--- stream_server_config
    content_by_lua_block {
        local sem = package.loaded.my_sema
        local ok, err = sem:wait(0.1)
        if not ok then
            ngx.say("failed to wait: ", err)
            return
        end
        ngx.say("sem wait successfully.")
    }
--- stream_response
sem wait successfully.
--- grep_error_log eval: qr/sem \w+: .*?,/
--- grep_error_log_out eval
[
"sem count: 2,
",
""
]
--- no_error_log
[error]



=== TEST 8: semaphore in preread_by_lua (all allowed)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    preread_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, "sem: ", err)
        end

        local ok, err = sem:wait(0.01)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        end

        sem:post(1)

        local count = sem:count()
        ngx.log(ngx.ERR, "sem: ", count)

        local ok, err = sem:wait(0.1)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        end
    }
    return "ok";
--- stream_response chop
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: timeout while prereading client data,
sem: 1 while prereading client data,
",
"sem: timeout while prereading client data,
sem: 1 while prereading client data,
",
]



=== TEST 9: semaphore in content_by_lua (all allowed)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, "sem: ", err)
        end

        local ok, err = sem:wait(0.01)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        end

        sem:post(1)

        local count = sem:count()
        ngx.log(ngx.ERR, "sem: ", count)

        local ok, err = sem:wait(0.1)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        else
            ngx.say("ok")
        end
    }
--- stream_response
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: timeout,
sem: 1,
",
"sem: timeout,
sem: 1,
",
]



=== TEST 10: semaphore in log_by_lua (wait not allowed)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    return "ok";
    log_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, "sem: ", err)
        end

        sem:post(1)

        local count = sem:count()
        ngx.log(ngx.ERR, "sem: ", count)

        local ok, err = sem:wait(0.1)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        end
    }
--- stream_response chop
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 1 while returning text,
sem: API disabled in the context of log_by_lua* while returning text,
",
"sem: 1 while returning text,
sem: API disabled in the context of log_by_lua* while returning text,
",
]
--- wait: 0.2



=== TEST 11: semaphore in ngx.timer (all allowed)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local function func_sem()
            local semaphore = require "ngx.semaphore"
            local sem, err = semaphore.new(0)
            if not sem then
                ngx.log(ngx.ERR, "sem: ", err)
            end

            local ok, err = sem:wait(0.01)
            if not ok then
                ngx.log(ngx.ERR, "sem: ", err)
            end

            sem:post(1)

            local count = sem:count()
            ngx.log(ngx.ERR, "sem: ", count)

            local ok, err = sem:wait(0.1)
            if not ok then
                ngx.log(ngx.ERR, "sem: ", err)
            end
        end

        local ok, err = ngx.timer.at(0, func_sem)
        if ok then
            ngx.sleep(0.01)
            ngx.say("ok")
        end
    }
--- stream_response
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: timeout,
sem: 1,
",
"sem: timeout,
sem: 1,
",
]
--- wait: 0.2



=== TEST 12: semaphore post in all phase (in a request)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_worker_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, err)
        end
        package.loaded.sem = sem

        local function wait()
            local i = 0
            while true do
                local ok, err = sem:wait(1)
                if not ok then
                    ngx.log(ngx.ERR, "sem: ", err)
                end
                i = i + 1
                if i % 3 == 0 then
                    ngx.log(ngx.ERR, "sem: 3 times")
                end
            end
        end

        local ok, err = ngx.timer.at(0, wait)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        end
    }
--- stream_server_config
    preread_by_lua_block {
        local sem = package.loaded.sem
        sem:post()
    }
    content_by_lua_block {
        local sem = package.loaded.sem
        sem:post()
        ngx.say("ok")
    }
    log_by_lua_block {
        local sem = package.loaded.sem
        sem:post()
    }
--- stream_response
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 3 times,
",
"sem: 3 times,
",
]
--- wait: 0.2



=== TEST 13: semaphore wait post in preread_by_lua
--- stream_config eval: $::HttpConfig
--- stream_server_config
    preread_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)

        local func_wait = function ()
            ngx.say("enter wait")

            local ok, err = sem:wait(1)
            if ok then
                ngx.say("wait success")
            end
        end
        local func_post = function ()
            ngx.say("enter post")

            sem:post()
            ngx.say("post success")
        end

        local co1 = ngx.thread.spawn(func_wait)
        local co2 = ngx.thread.spawn(func_post)

        ngx.thread.wait(co1)
        ngx.thread.wait(co2)
    }

    return "done";
--- stream_response chop
enter wait
enter post
post success
wait success
done
--- no_error_log
[error]



=== TEST 14: semaphore wait in timer.at
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new()

        local function func_wait(premature)
            local ok, err = sem:wait(1)
            if not ok then
                ngx.log(ngx.ERR, err)
            else
                ngx.log(ngx.ERR, "wait success")
            end
        end

        ngx.timer.at(0, func_wait)

        sem:post()
        ngx.sleep(0.01)
        ngx.say("ok")
    }
--- stream_response
ok
--- error_log
wait success



=== TEST 15: two thread wait for each other
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem_A = semaphore.new(0)
        local sem_B = semaphore.new(0)
        if not sem_A or not sem_B then
            error("create failed")
        end

        local function th_A()
            for i = 1, 11 do
                local ok, err = sem_A:wait(1)
                if not ok then
                    ngx.log(ngx.ERR, err)
                end
                sem_B:post(1)
            end
            ngx.say("count in A: ", sem_A:count())
        end
        local function th_B()
            for i = 1, 10 do
                local ok, err = sem_B:wait(1)
                if not ok then
                    ngx.log(ngx.ERR, err)
                end
                sem_A:post(1)
            end
            ngx.say("count in B: ", sem_B:count())
        end

        local co_A = ngx.thread.spawn(th_A)
        local co_B = ngx.thread.spawn(th_B)

        sem_A:post(1)
    }
--- log_level: debug
--- stream_response
count in B: 0
count in A: 0
--- no_error_log
[error]



=== TEST 16: kill a light thread that is waiting on a semaphore (no resource)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        if not sem then
            error("create failed")
        end

        local function func_wait()
            sem:wait(1)
        end
        local co = ngx.thread.spawn(func_wait)
        local ok, err = ngx.thread.kill(co)
        if ok then
            ngx.say("ok")
        else
            ngx.say(err)
        end
    }
--- log_level: debug
--- stream_response
ok
--- no_error_log
[error]



=== TEST 17: kill a light thread that is waiting on a semaphore (after post)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        if not sem then
            error("create failed")
        end

        local function func_wait()
            sem:wait(1)
        end
        local co = ngx.thread.spawn(func_wait)

        sem:post()
        local ok, err = ngx.thread.kill(co)

        if ok then
            ngx.say("ok")
        else
            ngx.say(err)
        end

        ngx.sleep(0.01)

        local count = sem:count()
        ngx.say("count: ", count)
    }
--- log_level: debug
--- stream_response
ok
count: 1
--- no_error_log
[error]



=== TEST 18: kill a thread that is waiting on another thread that is waiting on semaphore
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        if not sem then
            error("create failed")
        end

        local function sem_wait()
            ngx.say("sem waiting start")
            local ok, err = sem:wait(0.1)
            if not ok then
                ngx.say("sem wait err: ", err)
            end
            ngx.say("sem waiting done")
        end

        local function thread_wait()
            local co = ngx.thread.spawn(sem_wait)

            ngx.say("thread waiting start")
            local ok, err = ngx.thread.wait(co)
            if not ok then
                ngx.say("thread wait err: ", err)
            end
            ngx.say("thread waiting done")
        end

        local co2 = ngx.thread.spawn(thread_wait)
        ngx.sleep(0.01)

        local ok, err = ngx.thread.kill(co2)
        if ok then
            ngx.say("thread kill success")
        else
            ngx.say("kill err: ", err)
        end
    }
--- log_level: debug
--- stream_response
sem waiting start
thread waiting start
thread kill success
sem wait err: timeout
sem waiting done
--- no_error_log
[error]



=== TEST 19: a light thread that is going to exit is waiting on a semaphore
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        if not sem then
            error("create failed")
        end
        local function func(sem)
            ngx.say("sem waiting")
            local ok, err = sem:wait(0.1)
            if ok then
                ngx.say("wait success")
            else
                ngx.say("err: ", err)
            end
        end
        local co = ngx.thread.spawn(func, sem)
        ngx.say("ok")
        ngx.exit(200)
    }
--- log_level: debug
--- stream_response
sem waiting
ok
--- error_log
stream lua semaphore cleanup



=== TEST 20: main thread wait a light thread that is waiting on a semaphore
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        if not sem then
            error("create failed")
        end
        local function func(sem)
            local ok, err = sem:wait(0.001)
            if ok then
                ngx.say("wait success")
            else
                ngx.say("err: ", err)
            end
        end
        local co = ngx.thread.spawn(func, sem)
        ngx.thread.wait(co)
    }
--- log_level: debug
--- stream_response
err: timeout
--- no_error_log
[error]



=== TEST 21: multi wait and mult post with one semaphore
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if not sem then
            ngx.log(ngx.ERR, err)
            ngx.exit(500)
        end

        local function func(op, id)
            ngx.say(op, ": ", id)
            if op == "wait" then
                local ok, err = sem:wait(1)
                if ok then
                    ngx.say("wait success: ", id)
                end
            else
                sem:post()
            end
        end
        local tco = {}

        for i = 1, 3 do
            tco[#tco + 1] = ngx.thread.spawn(func, "wait", i)
        end

        for i = 1, 3 do
            tco[#tco + 1] = ngx.thread.spawn(func, "post", i)
        end

        for i = 1, #tco do
            ngx.thread.wait(tco[i])
        end
    }
--- stream_response
wait: 1
wait: 2
wait: 3
post: 1
post: 2
post: 3
wait success: 1
wait success: 2
wait success: 3
--- no_error_log
[error]



=== TEST 22: semaphore wait time is zero
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        local ok, err = sem:wait(0)
        if not ok then
            ngx.say(err)
        end
    }
--- stream_response
timeout
--- no_error_log
[error]



=== TEST 23: test semaphore gc
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem, err = semaphore.new(0)
        if sem then
            ngx.say("success")
        end
        sem = nil
        collectgarbage("collect")
    }
--- stream_response
success
--- log_level: debug
--- error_log
in lua gc, semaphore



=== TEST 24: basic semaphore_mm alloc
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(0)
        if sem then
            ngx.say("ok")
        end
    }
--- log_level: debug
--- stream_response
ok
--- grep_error_log eval: qr/(new block, alloc semaphore|from head of free queue, alloc semaphore)/
--- grep_error_log_out eval
[
"new block, alloc semaphore
",
"from head of free queue, alloc semaphore
",
]



=== TEST 25: basic semaphore_mm free insert tail
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sems = package.loaded.sems or {}
        package.loaded.sems = sems

        local num_per_block = 4095
        if not sems[num_per_block] then
            for i = 1, num_per_block * 3 do
                sems[i] = semaphore.new(0)
            end
        end

        for i = 1, 2 do
            if sems[i] then
                sems[i] = nil
                ngx.say("ok")
                break
            end
        end
        collectgarbage("collect")
    }
--- log_level: debug
--- stream_response
ok
--- error_log
add to free queue tail



=== TEST 26: basic semaphore_mm free insert head
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sems = package.loaded.sems or {}
        package.loaded.sems = sems

        local num_per_block = 4095
        if not sems[num_per_block] then
            for i = 1, num_per_block * 3 do
                sems[i] = semaphore.new(0)
            end
        end

        if sems[#sems] then
            sems[#sems] = nil
            ngx.say("ok")
        end
        collectgarbage("collect")
    }
--- log_level: debug
--- stream_response
ok
--- error_log
add to free queue head



=== TEST 27: semaphore_mm free block (load <= 50% & the on the older side)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sems = package.loaded.sems or {}
        package.loaded.sems = sems

        local num_per_block = 4095
        if not sems[num_per_block * 3] then
            for i = 1, num_per_block * 3 do
                sems[i] = semaphore.new(0)
            end

            for i = num_per_block + 1, num_per_block * 2 do
                sems[i] = nil
            end
        else
            for i = 1, num_per_block do
                sems[i] = nil
            end
        end

        collectgarbage("collect")
        ngx.say("ok")
    }
--- log_level: debug
--- stream_response
ok
--- grep_error_log eval: qr/free semaphore block/
--- grep_error_log_out eval
[
"",
"free semaphore block
",
]
--- timeout: 10



=== TEST 28: basic semaphore count
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new(10)
        local count = sem:count()
        ngx.say(count)

        sem:wait(0)
        local count = sem:count()
        ngx.say(count)

        sem:post(3)
        local count = sem:count()
        ngx.say(count)
    }
--- stream_response
10
9
12
--- no_error_log
[error]



=== TEST 29: basic semaphore count (negative number)
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sem = semaphore.new()
        local count = sem:count()
        ngx.say(count)

        local function wait()
            sem:wait(0.01)
        end
        local co = ngx.thread.spawn(wait)

        local count = sem:count()
        ngx.say(count)
    }
--- stream_response
0
-1
--- no_error_log
[error]



=== TEST 30: bugfix: semaphore instance can't be garbage collected when someone is waiting on it
--- stream_config eval: $::HttpConfig
--- stream_server_config
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"

        local my_sema = {}
        local key = "my key"

        local function my_clean()
            print("cleaning up")

            my_sema[key]:post()
            my_sema[key] = nil

            collectgarbage()
        end

        local ok, err = ngx.timer.at(0.001, my_clean)
        if not ok then
            ngx.log(ngx.ERR, "failed to create timer: ", err)
            ngx.exit(500)
        end

        my_sema[key] = semaphore:new(0)

        local ok, err = my_sema[key]:wait(2)
        ngx.say(ok, ", ", err)
    }
--- stream_response
true, nil
--- no_error_log
[error]
[crit]
