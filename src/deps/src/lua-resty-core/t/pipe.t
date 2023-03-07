# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 19) + 2;

add_block_preprocessor(sub {
    my $block = shift;

    my $http_config = $block->http_config || '';
    my $init_by_lua_block = $block->init_by_lua_block || '';

    $http_config .= <<_EOC_;
    lua_package_path '$t::TestCore::lua_package_path';
    init_by_lua_block {
        $t::TestCore::init_by_lua_block
        $init_by_lua_block
    }
_EOC_

    $block->set_value("http_config", $http_config);

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }
});

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();
$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::lua_package_path";

env_to_nginx("PATH");
no_long_string();
run_tests();

__DATA__

=== TEST 1: check pipe spawn arguments
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function check_error(...)
                local data, err = pcall(...)
                if not data then
                    ngx.say(err)
                else
                    ngx.say('ok')
                end
            end

            check_error(ngx_pipe.spawn, nil)
            check_error(ngx_pipe.spawn, {})
            check_error(ngx_pipe.spawn, {"ls"}, {buffer_size = 0})
            check_error(ngx_pipe.spawn, {"ls"}, {buffer_size = 0.5})
            check_error(ngx_pipe.spawn, {"ls"}, {buffer_size = "1"})
            check_error(ngx_pipe.spawn, {"ls"}, {buffer_size = true})
        }
    }
--- response_body
bad args arg: table expected, got nil
bad args arg: non-empty table expected
bad buffer_size option
bad buffer_size option
ok
bad buffer_size option



=== TEST 2: spawn process, with buffer_size option
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"ls"}, {buffer_size = 256})
            if not proc then
                ngx.say(err)
            else
                ngx.say('ok')
            end
        }
    }
--- response_body
ok
--- error_log eval
qr/lua pipe spawn process:[0-9A-F]+ pid:\d+ merge_stderr:0 buffer_size:256/
--- no_error_log
[error]



=== TEST 3: ensure process is destroyed in GC
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            do
                local proc, err = ngx_pipe.spawn({"ls", "-l"})
                if not proc then
                    ngx.say(err)
                    return
                end
            end

            collectgarbage()
            ngx.say("ok")
        }
    }
--- response_body
ok
--- no_error_log
[error]
--- error_log
lua pipe destroy process:



=== TEST 4: check phase for process wait
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 0.1})
            if not proc then
                ngx.say(err)
                return
            end

            package.loaded.proc = proc
        }

        log_by_lua_block {
            package.loaded.proc:wait()
        }
    }
--- error_log
API disabled in the context of log_by_lua



=== TEST 5: check process wait arguments
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 0.1})
            proc.wait()
        }
    }
--- error_code: 500
--- ignore_response_body
--- error_log eval
qr/\[error\] .*? runtime error: content_by_lua\(nginx\.conf\:\d+\):\d+: not a process instance/
--- no_error_log
[crit]



=== TEST 6: wait an already waited process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"ls"})
            if not proc then
                ngx.say(err)
                return
            end

            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
                return
            end

            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
exited



=== TEST 7: more than one coroutines wait a process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 0.1})
            if not proc then
                ngx.say(err)
                return
            end

            local function wait()
                local ok, err = proc:wait()
                if not ok then
                    ngx.say(err)
                end
            end

            local th1 = ngx.thread.spawn(wait)
            local th2 = ngx.thread.spawn(wait)
            ngx.thread.wait(th1)
            ngx.thread.wait(th2)
            ngx.thread.spawn(wait)
        }
    }
--- response_body
pipe busy waiting
exited



=== TEST 8: wait process, process exited abnormally before waiting
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sh", "-c", "sleep 0.1 && exit 2"})
            if not proc then
                ngx.say(err)
                return
            end

            ngx.sleep(0.2)
            local ok, reason, status = proc:wait()
            if ok == false then
                ngx.say(reason, " status: ", status)
            elseif ok == nil then
                ngx.say(reason)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
exit status: 2
--- no_error_log
[error]
--- error_log
lua pipe wait process:



=== TEST 9: wait process, process killed by signal before waiting
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "10s"})
            if not proc then
                ngx.say(err)
                return
            end

            -- sleep to ensure proc is already spawned under Valgrind
            ngx.sleep(0.2)
            os.execute("kill -INT " .. proc:pid())

            ngx.sleep(0.2)
            local ok, reason, status = proc:wait()
            if ok == false then
                ngx.say(reason, " status: ", status)
            elseif ok == nil then
                ngx.say(reason)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
--- response_body
signal status: 2
--- no_error_log
[error]
--- error_log
lua pipe wait process:



=== TEST 10: wait process, process exited before waiting
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 0.1})
            if not proc then
                ngx.say(err)
                return
            end

            ngx.sleep(0.2)
            local ok, reason, status = proc:wait()
            if ok ~= nil then
                ngx.say("ok: ", ok)
                ngx.say(reason, " status: ", status)
            else
                ngx.say(reason)
            end
        }
    }
--- response_body
ok: true
exit status: 0
--- no_error_log
[error]
--- error_log
lua pipe wait process:



=== TEST 11: pid() return process pid
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 0.1})
            if not proc then
                ngx.say(err)
                return
            end

            local pid = proc:pid()
            ngx.say("pid: ", pid, " type: ", type(pid))

            local ok, reason, status = proc:wait()
            if not ok then
                ngx.say(reason)
                return
            end

            pid = proc:pid()
            ngx.say("pid: ", pid, " type: ", type(pid))
        }
    }
--- response_body_like
pid: \d+ type: number
pid: \d+ type: number



=== TEST 12: wait process, aborted by uthread kill
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "10s"})
            if not proc then
                ngx.say(err)
                return
            end

            local function wait()
                proc:wait()
                ngx.log(ngx.ERR, "can't reach here")
            end

            local th = ngx.thread.spawn(wait)
            ngx.thread.kill(th)

            proc:set_timeouts(nil, nil, nil, 100)
            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
timeout
--- no_error_log
[error]
--- error_log
lua pipe wait process:
lua pipe proc wait cleanup



=== TEST 13: wait process which exited abnormally
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sh", "-c", "sleep 0.1 && exit 2"})
            if not proc then
                ngx.say(err)
                return
            end

            local ok, reason, status = proc:wait()
            if not ok then
                ngx.say(reason)
                ngx.say(status)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
exit
2



=== TEST 14: wait process which terminated by signal
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "5s"})
            if not proc then
                ngx.say(err)
                return
            end

            local pid = proc:pid()

            local function wait()
                local ok, reason, status = proc:wait()
                if not ok then
                    ngx.say(reason)
                    ngx.say(status)
                else
                    ngx.say("ok")
                end
            end

            ngx.thread.spawn(wait)
            -- sleep to ensure proc is already spawned under Valgrind
            ngx.sleep(0.2)
            os.execute("kill -TERM " .. pid)
        }
    }
--- response_body
signal
15



=== TEST 15: avoid set_timeouts overflow
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "5s"})
            if not proc then
                ngx.say(err)
                return
            end

            local function check_timeouts_overflow(write, stdout_read, stderr_read, wait)
                local ok, err = pcall(proc.set_timeouts, proc, write, stdout_read, stderr_read, wait)
                if not ok then
                    ngx.say("failed to set timeouts: ", err)
                else
                    ngx.say("set_timeouts: ok")
                end
            end

            ngx.say("write_timeout:")
            check_timeouts_overflow((2 ^ 32) - 1, 500, 500, 500)
            check_timeouts_overflow(2 ^ 32, 500, 500, 500)

            ngx.say("\nstdout_read_timeout:")
            check_timeouts_overflow(500, (2 ^ 32) - 1, 500, 500)
            check_timeouts_overflow(500, 2 ^ 32, 500, 500)

            ngx.say("\nstderr_read_timeout:")
            check_timeouts_overflow(500, 500, (2 ^ 32) - 1, 500)
            check_timeouts_overflow(500, 500, 2 ^ 32, 500)

            ngx.say("\nwait_timeout:")
            check_timeouts_overflow(500, 500, 500, (2 ^ 32) - 1)
            check_timeouts_overflow(500, 500, 500, 2 ^ 32)
        }
    }
--- response_body
write_timeout:
set_timeouts: ok
failed to set timeouts: bad write_timeout option

stdout_read_timeout:
set_timeouts: ok
failed to set timeouts: bad stdout_read_timeout option

stderr_read_timeout:
set_timeouts: ok
failed to set timeouts: bad stderr_read_timeout option

wait_timeout:
set_timeouts: ok
failed to set timeouts: bad wait_timeout option



=== TEST 16: avoid setting negative timeout
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "5s"})
            if not proc then
                ngx.say(err)
                return
            end

            local function check_timeouts(write, stdout_read, stderr_read, wait)
                local ok, err = pcall(proc.set_timeouts, proc, write, stdout_read, stderr_read, wait)
                if not ok then
                    ngx.say("failed to set timeouts: ", err)
                else
                    ngx.say("set_timeouts: ok")
                end
            end

            check_timeouts(0, 0, 0, 0)

            ngx.say("\nwrite_timeout:")
            check_timeouts(-1, 0, 0, 0)

            ngx.say("\nstdout_read_timeout:")
            check_timeouts(0, -1, 0, 0)

            ngx.say("\nstderr_read_timeout:")
            check_timeouts(0, 0, -1, 0)

            ngx.say("\nwait_timeout:")
            check_timeouts(0, 0, 0, -1)
        }
    }
--- response_body
set_timeouts: ok

write_timeout:
failed to set timeouts: bad write_timeout option

stdout_read_timeout:
failed to set timeouts: bad stdout_read_timeout option

stderr_read_timeout:
failed to set timeouts: bad stderr_read_timeout option

wait_timeout:
failed to set timeouts: bad wait_timeout option



=== TEST 17: wait process, timeout
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "10s"})
            if not proc then
                ngx.say(err)
                return
            end

            proc:set_timeouts(nil, nil, nil, 100)

            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
timeout
--- no_error_log
[error]
--- error_log
lua pipe wait process:
lua pipe add timer for waiting: 100(ms)



=== TEST 18: wait process, timeout, test for race condition
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            -- specify a larger timeout, so that there could be enough change
            -- to run posted event path
            local proc, err = ngx_pipe.spawn({"sleep", 1})
            if not proc then
                ngx.say(err)
                return
            end

            proc:set_timeouts(nil, nil, nil, 1000)

            local ok, err = proc:wait()
            if not ok and err ~= 'timeout' then
                ngx.say(err)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
ok



=== TEST 19: user case with send and shutdown
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function count_char(...)
                local proc = ngx_pipe.spawn({'wc', '-c'})
                local args = {...}
                for i = 1, #args do
                    local bytes, err = proc:write(args[i])
                    if not bytes then
                        ngx.say(err)
                        return
                    end
                end

                local ok, err = proc:shutdown('stdin')
                if not ok then
                    ngx.say(err)
                    return
                end

                local data, err = proc:stdout_read_line()
                if not data then
                    ngx.say(err)
                    return
                end

                ngx.say(data)
            end

            count_char('')
            count_char('a')
            count_char('hello')
            count_char(("1234"):rep(2048))
        }
    }
--- response_body
0
1
5
8192



=== TEST 20: shutdown before write/stdout_read/stderr_read
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo 'he\nllo' && >&2 echo 'wo\nrld'"})

            local function shutdown(direction)
                local ok, err = proc:shutdown(direction)
                if not ok then
                    ngx.log(ngx.ERR, err)
                end
            end

            shutdown('stdin')
            local ok, err = proc:write("test")
            if not ok then
                ngx.say("stdin: ", err)
            end

            shutdown('stdout')
            local ok, err = proc:stdout_read_line()
            if not ok then
                ngx.say("stdout: ", err)
            end

            shutdown('stderr')
            local ok, err = proc:stderr_read_line()
            if not ok then
                ngx.say("stderr: ", err)
            end
        }
    }
--- response_body
stdin: closed
stdout: closed
stderr: closed



=== TEST 21: shutdown after write/stdout_read/stderr_read
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo 'he\nllo' && >&2 echo 'wo\nrld'"})

            local function shutdown(direction)
                local ok, err = proc:shutdown(direction)
                if not ok then
                    ngx.log(ngx.ERR, err)
                end
            end

            proc:write("test")
            shutdown('stdin')
            local ok, err = proc:write("test")
            if not ok then
                ngx.say("stdin: ", err)
            end

            proc:stdout_read_line()
            shutdown('stdout')
            local ok, err = proc:stdout_read_line()
            if not ok then
                ngx.say("stdout: ", err)
            end

            proc:stderr_read_line()
            shutdown('stderr')
            local ok, err = proc:stderr_read_line()
            if not ok then
                ngx.say("stderr: ", err)
            end
        }
    }
--- response_body
stdin: closed
stdout: closed
stderr: closed



=== TEST 22: shutdown repeatedly is harmless
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo 'he\nllo' && >&2 echo 'wo\nrld'"})

            local function shutdown(direction)
                local ok, err = proc:shutdown(direction)
                if not ok then
                    ngx.log(ngx.ERR, err)
                end
            end

            proc:write("test")
            shutdown('stdin')
            shutdown('stdin')
            local ok, err = proc:write("test")
            if not ok then
                ngx.say("stdin: ", err)
            end

            proc:stdout_read_line()
            shutdown('stdout')
            shutdown('stdout')
            local ok, err = proc:stdout_read_line()
            if not ok then
                ngx.say("stdout: ", err)
            end

            proc:stderr_read_line()
            shutdown('stderr')
            shutdown('stderr')
            local ok, err = proc:stderr_read_line()
            if not ok then
                ngx.say("stderr: ", err)
            end
        }
    }
--- response_body
stdin: closed
stdout: closed
stderr: closed



=== TEST 23: shutdown unknown direction
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo hello && >&2 echo world"})

            local function shutdown(direction)
                local ok, err = pcall(proc.shutdown, proc, direction)
                if not ok then
                    ngx.say(err)
                end
            end

            shutdown("read")
            shutdown(0)
        }
    }
--- response_body
bad shutdown arg: read
bad shutdown arg: 0



=== TEST 24: shutdown a direction while a coroutine is waiting on it
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", "10s"})
            proc:set_timeouts(100, 100, 100)

            ngx.thread.spawn(function()
                local ok, err = proc:stdout_read_line()
                if not ok then
                    ngx.say("read stdout err: ", err)
                else
                    ngx.say("read stdout ok")
                end
            end)
            local ok, err = proc:shutdown('stdout')
            if not ok then
                ngx.say("shutdown stdout err: ", err)
            end

            ngx.thread.spawn(function()
                local ok, err = proc:stderr_read_line()
                if not ok then
                    ngx.say("read stderr err: ", err)
                else
                    ngx.say("read stderr ok")
                end
            end)
            local ok, err = proc:shutdown('stderr')
            if not ok then
                ngx.say("shutdown stderr err: ", err)
            end

            local data = ("1234"):rep(2048)
            local total = 0
            local step = #data
            -- make writers blocked later
            while true do
                local data, err = proc:write(data)
                if not data then
                    ngx.say("write stdin err: ", err)
                    break
                end

                total = total + step
                if total > 64 * step then
                    break
                end
            end

            ngx.thread.spawn(function()
                local ok, err = proc:write(data)
                if not ok then
                    ngx.say("write stdin err: ", err)
                else
                    ngx.say("write stdin ok")
                end
            end)
            local ok, err = proc:shutdown('stdin')
            if not ok then
                ngx.say("shutdown stdin err: ", err)
            end
        }
    }
--- response_body
read stdout err: aborted
read stderr err: aborted
write stdin err: timeout
write stdin err: aborted
--- no_error_log
[error]
--- grep_error_log eval
qr/lua pipe \w+ yielding/
--- grep_error_log_out
lua pipe read yielding
lua pipe read yielding
lua pipe write yielding
lua pipe write yielding



=== TEST 25: shutdown when merge_stderr is true
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local args = {"sh", "-c", "echo 'he\nllo' && >&2 echo 'wo\nrld'"}
            local opts = {merge_stderr = true}
            local function shutdown(proc, direction)
                local ok, err = proc:shutdown(direction)
                if not ok then
                    ngx.say("shutdown: ", err)
                end
            end

            local function read_proc(proc)
                local ok, err = proc:stdout_read_line()
                if not ok then
                    ngx.say("stdout: ", err)
                end
            end

            ngx.say("shutdown stdout after read")
            local proc = ngx_pipe.spawn(args, opts)
            proc:stdout_read_line()
            shutdown(proc, 'stdout')
            read_proc(proc)

            ngx.say("shutdown stdout before read")
            local proc = ngx_pipe.spawn(args, opts)
            shutdown(proc, 'stdout')
            read_proc(proc)

            ngx.say("shutdown stderr")
            local proc = ngx_pipe.spawn(args, opts)
            shutdown(proc, 'stderr')
        }
    }
--- response_body
shutdown stdout after read
stdout: closed
shutdown stdout before read
stdout: closed
shutdown stderr
shutdown: merged to stdout



=== TEST 26: interrupt signals which break io.popen should not break ngx.pipe IO
github issue openresty/resty-cli#35
--- http_config
    lua_sa_restart off;

--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local filename = "$TEST_NGINX_HTML_DIR/testfile"
            local f = io.open(filename, 'w')
            f:write("testfile")
            f:close()

            local proc = ngx_pipe.spawn({"openssl", "dgst", "-md5", filename})
            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body_like
MD5\([^)]+\)= 8bc944dbd052ef51652e70a5104492e3



=== TEST 27: ensure signals ignored by Nginx are reset.
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local binname = "$TEST_NGINX_HTML_DIR/sigpipe"
            local filename = "$TEST_NGINX_HTML_DIR/sigpipe.c"
            local f = io.open(filename, 'w')
            f:write([[
                #include <unistd.h>
                #include <stdio.h>
                #include <sys/types.h>
                #include <signal.h>

                int main(void)
                {
                    kill(getpid(), SIGPIPE);
                    printf("I was not killed by SIGPIPE\n");
                    return 0;
                }
            ]])
            f:close()

            local cmd = "gcc " .. filename .. " -o " .. binname
            local proc, err = ngx_pipe.spawn({"sh", "-c", cmd})
            if not proc then
                ngx.say("spawn ", cmd, " failed: ", err)
                return
            end

            local msg = proc:stderr_read_all()
            local ok = proc:wait()
            if not ok then
                ngx.say("wait failed: ", msg)
                return
            end

            local proc, err = ngx_pipe.spawn({binname})
            if not proc then
                ngx.say("spawn ", binname, " failed: ", err)
                return
            end

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
closed



=== TEST 28: ensure spawning process in init_by_lua is disabled.
--- init_by_lua_block
    local ngx_pipe = require "ngx.pipe"

    local ok, err = pcall(ngx_pipe.spawn, {"echo", "hello world"})
    if not ok then
        package.loaded.res = err
    end
--- config
    location = /t {
        content_by_lua_block {
            ngx.say(package.loaded.res)
        }
    }
--- response_body
API disabled in the current context



=== TEST 29: interact with bc
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local proc = ngx_pipe.spawn({"bc"}, {merge_stderr = true})
            proc:set_timeouts(1000, 1000, 1000)

            local function check_call(proc, func, ...)
                local data, err = func(proc, ...)
                if not data then
                    ngx.say("ERR: ", err)
                    ngx.exit(ngx.OK)
                else
                    ngx.log(ngx.WARN, "bc say ", data)
                end
            end

            local step = 0.05
            ngx.sleep(step)

            proc:write("1 + 2\n")
            ngx.sleep(step)
            check_call(proc, proc.stdout_read_any, 1024)

            proc:write("2 ^ 3\n")
            ngx.sleep(step)
            check_call(proc, proc.stdout_read_any, 1024)

            proc:write("quit\n")

            local ok, reason, status = proc:wait()
            if not ok then
                ngx.say(reason)
                ngx.say(status)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
ok
--- no_error_log
[error]
--- error_log
bc say 3
bc say 8



=== TEST 30: allow to specify nil as terminator
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local args = {"sh", "-c", "echo hello", nil, "echo world"}
            local proc, err = ngx_pipe.spawn(args)
            if not proc then
                ngx.say(err)
                return
            end

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello



=== TEST 31: specify a string to spawn works like os.execute
--- config
    location = /t {
        content_by_lua_block {
            collectgarbage()
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn("echo 'hello' && >&2 echo 'world'")

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say("stdout: ", err)
            else
                ngx.say("stdout: ", data)
            end

            local data, err = proc:stderr_read_line()
            if not data then
                ngx.say("stderr: ", err)
            else
                ngx.say("stderr: ", data)
            end
        }
    }
--- response_body
stdout: hello
stderr: world



=== TEST 32: wait process which executed failed
When execvp failed, we let OS free the memory. Therefore we have to skip this
test under Valgrind mode.
--- skip_eval: 3: defined $ENV{TEST_NGINX_USE_VALGRIND}
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"/exit", "2"})
            if not proc then
                ngx.say(err)
                return
            end

            local ok, reason, status = proc:wait()
            if not ok then
                ngx.say(reason)
                ngx.say(status)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
exit
1
--- error_log
lua pipe child execvp() failed while executing /exit (2: No such file or directory)



=== TEST 33: wait process, process exited normally after waiting
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 0.1})
            if not proc then
                ngx.say(err)
                return
            end

            local ok, reason, status = proc:wait()
            if ok ~= nil then
                ngx.say("ok: ", ok)
                ngx.say(reason, " status: ", status)
            else
                ngx.say(reason)
            end
        }
    }
--- response_body
ok: true
exit status: 0
--- no_error_log
[error]
--- error_log
lua pipe wait process:



=== TEST 34: kill process with invalid signal
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", 10})

            local function check_pcall(f, ...)
                local ok, err = pcall(f, ...)
                if not ok then
                    ngx.say(err)
                end
            end

            local function check_call(f, ...)
                local ok, err = f(...)
                if not ok then
                    ngx.say(err)
                end
            end

            check_pcall(proc.kill, proc)
            check_call(proc.kill, proc, 10000)
        }
    }
--- response_body
bad signal arg: number expected, got nil
invalid signal



=== TEST 35: kill exited process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", 0.1})

            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
                return
            end

            local function check_call(f, ...)
                local ok, err = f(...)
                if not ok then
                    ngx.say(err)
                end
            end

            local SIGKILL = 9
            check_call(proc.kill, proc, SIGKILL)

            proc = ngx_pipe.spawn({"sleep", 0.1})
            ngx.sleep(0.5)
            check_call(proc.kill, proc, SIGKILL)
        }
    }
--- response_body
exited
exited



=== TEST 36: wait process which is terminated by a signal, using proc.kill
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "5s"})
            if not proc then
                ngx.say(err)
                return
            end

            local pid = proc:pid()

            local function wait()
                local ok, reason, status = proc:wait()
                if not ok then
                    ngx.say(reason)
                    ngx.say(status)
                else
                    ngx.say("ok")
                end
            end

            ngx.thread.spawn(wait)
            -- sleep to ensure proc is already spawned under Valgrind
            ngx.sleep(0.2)

            local SIGTERM = 15
            local ok, err = proc:kill(SIGTERM)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
signal
15



=== TEST 37: kill living sub-process when the process instance is collected by GC.
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            do
                local proc, err = ngx_pipe.spawn({"sleep", 3600})
                if not proc then
                    ngx.say(err)
                    return
                end
            end

            collectgarbage()
            ngx.say("ok")
        }
    }
--- response_body
ok
--- no_error_log
[error]
--- error_log
lua pipe destroy process:
lua pipe kill process:



=== TEST 38: kill living sub-process during Lua VM destruction.
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 3600})
            if not proc then
                ngx.say(err)
                return
            end

            ngx.say("ok")
        }
    }
--- response_body
ok
--- error_log
lua pipe destroy process:
lua pipe kill process:
--- no_shutdown_error_log
lua pipe destroy process:
lua pipe kill process:



=== TEST 39: avoided overwritting log fd when stderr is used as destination.
--- config
    location = /t {
        content_by_lua_block {
            local function get_ngx_bin_path()
                local ffi = require "ffi"
                ffi.cdef[[char **ngx_argv;]]
                return ffi.string(ffi.C.ngx_argv[0])
            end

            local conf_file = "$TEST_NGINX_HTML_DIR/nginx.conf"
            local nginx = get_ngx_bin_path()

            local cmd = nginx .. " -p $TEST_NGINX_HTML_DIR -c " .. conf_file
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn(cmd)
            if not proc then
                ngx.log(ngx.ERR, err)
                return
            end

            local data, err = proc:stderr_read_all()
            if not data then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.say(data)
        }
    }
--- user_files
>>> nginx.conf
events {
    worker_connections 64;
}
error_log stderr error;
daemon off;
master_process off;
worker_processes 1;
http {
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_worker_by_lua_block {
        ngx.timer.at(0, function()
            require "ngx.pipe".spawn{"no-such-cmd"}:wait()
            os.exit(0)
        end)
    }
}
>>> logs/error.log
--- response_body_like
lua pipe child execvp\(\) failed while executing no-such-cmd \(2: No such file or directory\)



=== TEST 40: avoid shell cmd's constants being GCed
--- init_by_lua_block
    local ngx_pipe = require "ngx.pipe"
    package.loaded.pipe = ngx_pipe

--- config
    location = /t {
        content_by_lua_block {
            collectgarbage()
            local proc, err = package.loaded.pipe.spawn("wc --help")
            if not proc then
                ngx.say(err)
                return
            end

            local ok, reason, status = proc:wait()
            if not ok then
                ngx.say(reason)
                ngx.say(status)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
ok



=== TEST 41: log the signal info like what Nginx does for SIGCHLD
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"ls"})
            if not proc then
                ngx.say(err)
                return
            end

            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
                return
            end
            ngx.say('ok')
        }
    }
--- response_body
ok
--- error_log eval
qr/\[notice\] .* signal \d+ \(SIGCHLD\) received from \d+/
--- no_error_log
[error]



=== TEST 42: return nil plus string 'timeout' when waiting process timed out
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", "10s"})
            if not proc then
                ngx.say(err)
                return
            end

            proc:set_timeouts(nil, nil, nil, 10)
            local ok, err = proc:wait()
            if not ok then
                ngx.say(ok)
                ngx.say(err)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
nil
timeout
--- no_error_log
[error]
--- error_log
lua pipe wait process:



=== TEST 43: spawn sub-process when error_log is configured with syslog
--- config
    location = /t {
        content_by_lua_block {
            local function get_ngx_bin_path()
                local ffi = require "ffi"
                ffi.cdef[[char **ngx_argv;]]
                return ffi.string(ffi.C.ngx_argv[0])
            end

            local conf_file = "$TEST_NGINX_HTML_DIR/nginx.conf"
            local nginx = get_ngx_bin_path()

            local cmd = nginx .. " -p $TEST_NGINX_HTML_DIR -c " .. conf_file
            local ngx_pipe = require "ngx.pipe"
            local ok, reason, status = ngx_pipe.spawn(cmd):wait()
            ngx.say(ok)
            ngx.say(reason)
            ngx.say(status)
        }
    }
--- user_files
>>> nginx.conf
events {
    worker_connections 64;
}
error_log  syslog:server=127.0.0.1:$TEST_NGINX_MEMCACHED_PORT,facility=local1 info;
daemon off;
master_process off;
worker_processes 1;
http {
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    init_worker_by_lua_block {
        ngx.timer.at(0, function()
            local ngx_pipe = require "ngx.pipe"
            local ok, reason, status = ngx_pipe.spawn("echo"):wait()
            if not ok then
                os.exit(status)
            end
            os.exit(0)
        end)
    }
}
>>> logs/error.log
--- response_body
true
exit
0
--- no_error_log
[error]



=== TEST 44: wait process, aborted by uthread kill, with graceful shutdown
--- user_files
>>> a.lua
local ngx_pipe = require "ngx.pipe"
local proc = ngx_pipe.spawn({"bash"})

local function func()
    proc:wait()
    ngx.log(ngx.ERR, "can't reach here")
end

local th = ngx.thread.spawn(func)
ngx.thread.kill(th)

local data, err = proc:kill(9)
if not data then
    io.stdout:write("proc:kill(9) err: ", err)
else
    io.stdout:write("ok")
end

--- config
    location = /t {
        content_by_lua_block {
            local helper = require "helper"
            local f = io.open("$TEST_NGINX_HTML_DIR/a.lua")
            local code = f:read("*a")
            local proc = helper.run_lua_with_graceful_shutdown("$TEST_NGINX_HTML_DIR", code)
            proc:set_timeouts(300, 300, 300, 300)

            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say("stdout err: ", err)
            else
                ngx.say("stdout: ", data)
            end

            local data, err = proc:stderr_read_any(4096)
            if not data then
                ngx.say("stderr err: ", err)
            else
                ngx.say("stderr: ", data)
            end
        }
    }
--- response_body
stdout: ok
stderr err: closed
--- no_error_log
[error]



=== TEST 45: spawn process, with environ option (sanity)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local proc, err = ngx_pipe.spawn('echo $TEST_ENV', {
                environ = { "TEST_ENV=blahblah" }
            })
            if not proc then
                ngx.say(err)
                return
            end

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
blahblah



=== TEST 46: spawn process, with environ option (multiple values)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local proc, err = ngx_pipe.spawn('echo "$TEST_ENV $TEST_FOO"', {
                environ = { "TEST_ENV=blahblah", "TEST_FOO=hello" }
            })
            if not proc then
                ngx.say(err)
                return
            end

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
blahblah hello



=== TEST 47: spawn process, with empty environ option (no values)
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local proc, err = ngx_pipe.spawn('echo "TEST_ENV:$TEST_ENV"', {
                environ = {}
            })
            if not proc then
                ngx.say(err)
                return
            end

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
TEST_ENV:



=== TEST 48: spawn process, with invalid environ option
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function spawn(environ)
                local pok, perr = pcall(ngx_pipe.spawn, 'echo $TEST_ENV', {
                    environ = environ
                })
                if not pok then
                    ngx.say(perr)
                else
                    ngx.say("ok")
                end
            end

            spawn("TEST_ENV=1")
            spawn({ "TEST_ENV=", 1 })
            spawn({ "TEST_ENV" })
            spawn({ "=1" })
        }
    }
--- response_body
bad environ option: table expected, got string
bad value at index 2 of environ option: string expected, got number
bad value at index 1 of environ option: 'name=[value]' format expected, got 'TEST_ENV'
bad value at index 1 of environ option: 'name=[value]' format expected, got '=1'



=== TEST 49: spawn process, with invalid environ option
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function spawn(environ)
                local pok, perr = pcall(ngx_pipe.spawn, 'echo "TEST_ENV:$TEST_ENV"', {
                    environ = environ
                })
                if not pok then
                    ngx.say(perr)
                    return
                end

                local proc = perr

                local data, err = proc:stdout_read_line()
                if not data then
                    ngx.say(err)
                else
                    ngx.say(data)
                end
            end

            spawn({ "TEST_ENV =1" })
            spawn({ "TEST_ENV= 1" })
            spawn({ "TEST_ENV==1" })
        }
    }
--- response_body
TEST_ENV:
TEST_ENV: 1
TEST_ENV:=1



=== TEST 50: spawn process, with environ option containing nil holes
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function spawn(environ)
                local proc, err = ngx_pipe.spawn('echo "$TEST_ENV2$TEST_ENV"', {
                    environ = environ
                })
                if not proc then
                    ngx.say(err)
                    return
                end

                local data, err = proc:stdout_read_line()
                if not data then
                    ngx.say(err)
                else
                    ngx.say(data)
                end
            end

            spawn({ "TEST_ENV=1", nil, "TEST_ENV2=2", nil })
            spawn({ "TEST_ENV=1", nil, "TEST_ENV2=2" })
            spawn({ nil, "TEST_ENV=1", "TEST_ENV2=2"})
            spawn({ hash_key = true, "TEST_ENV=1", nil, "TEST_ENV2=2", nil })
            spawn({ hash_key = true, "TEST_ENV=1", nil, "TEST_ENV2=2" })
        }
    }
--- response_body
1
1

1
1



=== TEST 51: spawn process with wait_timeout option
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc, err = ngx_pipe.spawn({"sleep", 1}, {
                wait_timeout = 100
            })

            local ok, err = proc:wait()
            if not ok then
                ngx.say(err)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
timeout



=== TEST 52: validate timeout options when spawning process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function spawn(opts)
                local ok, err = pcall(ngx_pipe.spawn, {"sleep", "5s"}, opts)
                if not ok then
                    ngx.say(err)
                else
                    ngx.say("ok")
                end
            end

            ngx.say("write_timeout:")
            spawn({write_timeout = 2 ^ 32})
            spawn({write_timeout = -1})

            ngx.say("\nstdout_read_timeout:")
            spawn({stdout_read_timeout = 2 ^ 32})
            spawn({stdout_read_timeout = -1})

            ngx.say("\nstderr_read_timeout:")
            spawn({stderr_read_timeout = 2 ^ 32})
            spawn({stderr_read_timeout = -1})

            ngx.say("\nwait_timeout:")
            spawn({wait_timeout = 2 ^ 32})
            spawn({wait_timeout = -1})
        }
    }
--- response_body
write_timeout:
bad write_timeout option
bad write_timeout option

stdout_read_timeout:
bad stdout_read_timeout option
bad stdout_read_timeout option

stderr_read_timeout:
bad stderr_read_timeout option
bad stderr_read_timeout option

wait_timeout:
bad wait_timeout option
bad wait_timeout option



=== TEST 53: validate timeout options when spawning process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"

            local function spawn(opts)
                local ok, err = pcall(ngx_pipe.spawn, {"sleep", "5s"}, opts)
                if not ok then
                    ngx.log(ngx.ERR, err)
                end
            end

            spawn({write_timeout = -1})
            spawn({stdout_read_timeout = -1})
            spawn({stderr_read_timeout = -1})
            spawn({wait_timeout = -1})
        }
    }
--- ignore_response_body
--- error_log eval
[
    qr/\[error\] .*? content_by_lua\(nginx\.conf:\d+\):\d+: .*? bad write_timeout option/,
    qr/\[error\] .*? content_by_lua\(nginx\.conf:\d+\):\d+: .*? bad stdout_read_timeout option/,
    qr/\[error\] .*? content_by_lua\(nginx\.conf:\d+\):\d+: .*? bad stderr_read_timeout option/,
    qr/\[error\] .*? content_by_lua\(nginx\.conf:\d+\):\d+: .*? bad wait_timeout option/
]
--- no_error_log
[crit]
