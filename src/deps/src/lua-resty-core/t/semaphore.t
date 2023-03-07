# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(10140);
#workers(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 3);

no_long_string();
#no_diff();
$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::lua_package_path";
our $HttpConfig = <<_EOC_;
    lua_package_path "$t::TestCore::lua_package_path";
_EOC_

run_tests();

__DATA__

=== TEST 1: basic semaphore in uthread
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
enter waiting
back in main thread
still in main thread
wait success
main thread end
--- no_error_log
[error]



=== TEST 2: semaphore wait order
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
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
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
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



=== TEST 4: basic semaphore in subrequest
--- http_config eval: $::HttpConfig
--- config
    location = /test {
        content_by_lua_block {
            local res1, res2 = ngx.location.capture_multi{
                { "/sem_wait"},
                { "/sem_post"},
            }
            ngx.say(res1.status)
            ngx.say(res1.body)
            ngx.say(res2.status)
            ngx.say(res2.body)
        }
    }

    location /sem_wait {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            local g = package.loaded["semaphore_test"] or {}
            package.loaded["semaphore_test"] = g

            if not g.test then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.say(err)
                    return
                end
                g.test = sem
            end
            local sem = g.test
            local ok, err = sem:wait(1)
            if ok then
                ngx.print("wait")
            end
        }
    }

    location /sem_post {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            local g = package.loaded["semaphore_test"] or {}
            package.loaded["semaphore_test"] = g

            if not g.test then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.say(err)
                    ngx.exit(500)
                end
                g.test = sem
            end
            local sem = g.test
            ngx.sleep(0.001)
            collectgarbage("collect")
            sem:post()
            ngx.print("post")
        }
    }
--- request
GET /test
--- response_body
200
wait
200
post
--- no_error_log
[error]
[crit]



=== TEST 5: semaphore.new in init_by_lua* (w/o shdict)
--- http_config
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
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body_like
sem count: [12]
waited successfully.
--- grep_error_log eval
qr/\[lua\] init_by_lua\(nginx.conf:\d+\):\d+: sema created: table: 0x[a-f0-9]+/
--- grep_error_log_out eval
[
qr/\[lua\] init_by_lua\(nginx.conf:\d+\):\d+: sema created: table: 0x[a-f0-9]+/,
"",
]



=== TEST 6: semaphore.new in init_by_lua* (with shdict)
--- http_config
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
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body_like
sem count: [12]
waited successfully.
--- grep_error_log eval
qr/\[lua\] init_by_lua\(nginx.conf:\d+\):\d+: sema created: table: 0x[a-f0-9]+/
--- grep_error_log_out eval
[
qr/\[lua\] init_by_lua\(nginx.conf:\d+\):\d+: sema created: table: 0x[a-f0-9]+/,
"",
]



=== TEST 7: semaphore in init_worker_by_lua (wait is not allowed)
--- http_config
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
--- config
    location /t {
        echo "ok";
    }
--- request
GET /t
--- response_body
ok
--- grep_error_log eval: qr/sem \w+: .*?,/
--- grep_error_log_out eval
[
"sem count: 1,
sem wait: API disabled in the context of init_worker_by_lua*,
",
"",
]



=== TEST 8: semaphore in init_worker_by_lua (new and post)
--- http_config
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
--- config
    location /t {
        content_by_lua_block {
            local sem = package.loaded.my_sema
            local ok, err = sem:wait(0.1)
            if not ok then
                ngx.say("failed to wait: ", err)
                return
            end
            ngx.say("sem wait successfully.")
        }
    }
--- request
GET /t
--- response_body
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



=== TEST 9: semaphore in set_by_lua (wait is not allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        set_by_lua_block $res {
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
        echo "ok";
    }
--- request
GET /t
--- response_body
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 1,
sem: API disabled in the context of set_by_lua*,
",
"sem: 1,
sem: API disabled in the context of set_by_lua*,
",
]



=== TEST 10: semaphore in rewrite_by_lua (all allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        rewrite_by_lua_block {
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
        echo "ok";
    }
--- request
GET /t
--- response_body
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



=== TEST 11: semaphore in access_by_lua (all allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        access_by_lua_block {
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
        echo "ok";
    }
--- request
GET /t
--- response_body
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



=== TEST 12: semaphore in content_by_lua (all allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
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
    }
--- request
GET /t
--- response_body
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



=== TEST 13: semaphore in log_by_lua (wait not allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        echo "ok";
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
    }
--- request
GET /t
--- response_body
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 1 while logging request,
sem: API disabled in the context of log_by_lua* while logging request,
",
"sem: 1 while logging request,
sem: API disabled in the context of log_by_lua* while logging request,
",
]
--- wait: 0.2



=== TEST 14: semaphore in header_filter_by_lua (wait not allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        echo "ok";
        header_filter_by_lua_block {
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
    }
--- request
GET /t
--- response_body
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 1,
sem: API disabled in the context of header_filter_by_lua*,
",
"sem: 1,
sem: API disabled in the context of header_filter_by_lua*,
",
]



=== TEST 15: semaphore in body_filter_by_lua (wait not allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        echo "ok";
        body_filter_by_lua_block {
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
    }
--- request
GET /t
--- response_body
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 1,
sem: API disabled in the context of body_filter_by_lua*,
sem: 1,
sem: API disabled in the context of body_filter_by_lua*,
",
"sem: 1,
sem: API disabled in the context of body_filter_by_lua*,
sem: 1,
sem: API disabled in the context of body_filter_by_lua*,
",
]



=== TEST 16: semaphore in ngx.timer (all allowed)
--- http_config eval: $::HttpConfig
--- config
    location /t {
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
    }
--- request
GET /t
--- response_body
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



=== TEST 17: semaphore post in all phase (in a request)
--- http_config
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
                if i % 6 == 0 then
                    ngx.log(ngx.ERR, "sem: 6 times")
                end
            end
        end

        local ok, err = ngx.timer.at(0, wait)
        if not ok then
            ngx.log(ngx.ERR, "sem: ", err)
        end
    }
--- config
    location /test {
        set_by_lua_block $res {
            local sem = package.loaded.sem
            sem:post()
        }
        rewrite_by_lua_block {
            local sem = package.loaded.sem
            sem:post()
        }
        access_by_lua_block {
            local sem = package.loaded.sem
            sem:post()
        }
        content_by_lua_block {
            local sem = package.loaded.sem
            sem:post()
            ngx.say("ok")
        }
        header_filter_by_lua_block {
            local sem = package.loaded.sem
            sem:post()
        }
        body_filter_by_lua_block {
            local sem = package.loaded.sem
            sem:post()
        }
    }
--- request
GET /test
--- response_body
ok
--- grep_error_log eval: qr/sem: .*?,/
--- grep_error_log_out eval
[
"sem: 6 times,
",
"sem: 6 times,
",
]
--- wait: 0.2



=== TEST 18: semaphore wait post in access_by_lua
--- http_config eval: $::HttpConfig
--- config
    location /test {
        access_by_lua_block {
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
    }
--- request
GET /test
--- response_body
enter wait
enter post
post success
wait success
--- no_error_log
[error]



=== TEST 19: semaphore wait post in rewrite_by_lua
--- http_config eval: $::HttpConfig
--- config
    location /t {
        rewrite_by_lua_block {
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
    }
--- request
GET /test
--- response_body
enter wait
enter post
post success
wait success
--- no_error_log
[error]



=== TEST 20: semaphore wait in timer.at
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
ok
--- error_log
wait success



=== TEST 21: semaphore post in header_filter_by_lua (subrequest)
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local res1, res2 = ngx.location.capture_multi{
                {"/sem_wait"},
                {"/sem_post"},
            }
            ngx.say(res1.status)
            ngx.say(res1.body)
            ngx.say(res2.status)
            ngx.say(res2.body)
        }
    }

    location /sem_wait {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            if not package.loaded.sem then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.say(err)
                    ngx.exit(500)
                end
                package.loaded.sem = sem
            end
            local sem = package.loaded.sem
            local ok, err = sem:wait(1)
            if ok then
                ngx.print("wait")
                ngx.exit(200)
            else
                ngx.exit(500)
            end
        }
    }

    location /sem_post {
        header_filter_by_lua_block {
            local semaphore = require "ngx.semaphore"
            if not package.loaded.sem then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.log(ngx.ERR, err)
                end
                package.loaded.sem = sem
            end
            local sem = package.loaded.sem
            sem:post()
        }

        content_by_lua_block {
            ngx.print("post")
            ngx.exit(200)
        }
    }
--- request
GET /test
--- response_body
200
wait
200
post
--- no_error_log
[error]



=== TEST 22: semaphore post in body_filter_by_lua (subrequest)
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local res1, res2 = ngx.location.capture_multi{
                {"/sem_wait"},
                {"/sem_post"},
            }
            ngx.say(res1.status)
            ngx.say(res1.body)
            ngx.say(res2.status)
            ngx.say(res2.body)
        }
    }

    location /sem_wait {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            if not package.loaded.sem then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.say(err)
                    ngx.exit(500)
                end
                package.loaded.sem = sem
            end
            local sem = package.loaded.sem
            local ok, err = sem:wait(10)
            if ok then
                ngx.print("wait")
                ngx.exit(200)
            else
                ngx.exit(500)
            end
        }
    }

    location /sem_post {
        body_filter_by_lua_block {
            local semaphore = require "ngx.semaphore"
            if not package.loaded.sem then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.log(ngx.ERR, err)
                end
                package.loaded.sem = sem
            end
            local sem = package.loaded.sem
            sem:post()
        }

        content_by_lua_block {
            ngx.print("post")
            ngx.exit(200)
        }
    }
--- request
GET /test
--- response_body
200
wait
200
post
--- log_level: debug
--- no_error_log
[error]



=== TEST 23: semaphore post in set_by_lua
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local res1, res2 = ngx.location.capture_multi{
                {"/sem_wait"},
                {"/sem_post"},
            }
            ngx.say(res1.status)
            ngx.say(res1.body)
            ngx.say(res2.status)
            ngx.say(res2.body)
        }
    }

    location /sem_wait {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            if not package.loaded.sem then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.say(err)
                    ngx.exit(500)
                end
                package.loaded.sem = sem
            end
            local sem = package.loaded.sem
            local ok, err = sem:wait(10)
            if ok then
                ngx.print("wait")
                ngx.exit(200)
            else
                ngx.exit(500)
            end
        }
    }

    location /sem_post {
        set_by_lua_block $res {
            local semaphore = require "ngx.semaphore"
            if not package.loaded.sem then
                local sem, err = semaphore.new(0)
                if not sem then
                    ngx.log(ngx.ERR, err)
                end
                package.loaded.sem = sem
            end
            local sem = package.loaded.sem
            sem:post()
        }
        content_by_lua_block {
            ngx.print("post")
            ngx.exit(200)
        }
    }
--- request
GET /test
--- response_body
200
wait
200
post
--- log_level: debug
--- no_error_log
[error]



=== TEST 24: semaphore post in timer.at
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            package.loaded.sem = semaphore.new(0)
            local res1, res2 = ngx.location.capture_multi{
                {"/sem_wait"},
                {"/sem_post"},
            }
            ngx.say(res1.status)
            ngx.say(res1.body)
            ngx.say(res2.status)
            ngx.say(res2.body)
        }
    }

    location /sem_wait {
        content_by_lua_block {
            local sem = package.loaded.sem
            local ok, err = sem:wait(2)
            if ok then
                ngx.print("wait")
                ngx.exit(200)
            else
                ngx.status = 500
                ngx.say(err)
            end
        }
    }

    location /sem_post {
        content_by_lua_block {
            local function func(premature)
                local sem = package.loaded.sem
                sem:post()
            end
            ngx.timer.at(0, func, g)
            ngx.sleep(0)
            ngx.print("post")
            ngx.exit(200)
        }
    }
--- request
GET /test
--- response_body
200
wait
200
post
--- log_level: debug
--- no_error_log
[error]



=== TEST 25: two thread wait for each other
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
count in B: 0
count in A: 0
--- no_error_log
[error]



=== TEST 26: kill a light thread that is waiting on a semaphore (no resource)
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
ok
--- no_error_log
[error]



=== TEST 27: kill a light thread that is waiting on a semaphore (after post)
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
ok
count: 1
--- no_error_log
[error]



=== TEST 28: kill a thread that is waiting on another thread that is waiting on semaphore
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
sem waiting start
thread waiting start
thread kill success
sem wait err: timeout
sem waiting done
--- no_error_log
[error]



=== TEST 29: a light thread that is going to exit is waiting on a semaphore
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
sem waiting
ok
--- error_log
http lua semaphore cleanup



=== TEST 30: main thread wait a light thread that is waiting on a semaphore
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
err: timeout
--- no_error_log
[error]



=== TEST 31: multi wait and mult post with one semaphore
--- http_config eval: $::HttpConfig
--- config
    location = /test {
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
    }
--- request
GET /test
--- response_body
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



=== TEST 32: semaphore wait time is zero
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            local sem = semaphore.new(0)
            local ok, err = sem:wait(0)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- request
GET /test
--- response_body
timeout
--- no_error_log
[error]



=== TEST 33: test semaphore gc
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            local sem, err = semaphore.new(0)
            if sem then
                ngx.say("success")
            end
            sem = nil
            collectgarbage("collect")
        }
    }
--- request
GET /test
--- response_body
success
--- log_level: debug
--- error_log
in lua gc, semaphore



=== TEST 34: basic semaphore_mm alloc
--- http_config eval: $::HttpConfig
--- config
    location /test {
        content_by_lua_block {
            local semaphore = require "ngx.semaphore"
            local sem = semaphore.new(0)
            if sem then
                ngx.say("ok")
            end
        }
    }
--- log_level: debug
--- request
GET /test
--- response_body
ok
--- grep_error_log eval: qr/(new block, alloc semaphore|from head of free queue, alloc semaphore)/
--- grep_error_log_out eval
[
"new block, alloc semaphore
",
"from head of free queue, alloc semaphore
",
]



=== TEST 35: basic semaphore_mm free insert tail
--- http_config eval: $::HttpConfig
--- config
    location /t {
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
    }
--- log_level: debug
--- request
GET /t
--- response_body
ok
--- error_log
add to free queue tail



=== TEST 36: basic semaphore_mm free insert head
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
ok
--- error_log
add to free queue head



=== TEST 37: semaphore_mm free block (load <= 50% & the on the older side)
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- log_level: debug
--- request
GET /test
--- response_body
ok
--- grep_error_log eval: qr/free semaphore block/
--- grep_error_log_out eval
[
"",
"free semaphore block
",
]
--- timeout: 10



=== TEST 38: basic semaphore count
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
10
9
12
--- no_error_log
[error]



=== TEST 39: basic semaphore count (negative number)
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
0
-1
--- no_error_log
[error]



=== TEST 40: bugfix: semaphore instance can't be garbage collected when someone is waiting on it
--- http_config eval: $::HttpConfig
--- config
    location /test {
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
    }
--- request
GET /test
--- response_body
true, nil
--- no_error_log
[error]
[crit]
