# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;
use Cwd qw(abs_path realpath cwd);
use File::Basename;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 6);

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

$ENV{TEST_NGINX_CERT_DIR} ||= dirname(realpath(abs_path(__FILE__)));
my $port = server_port;
if ($port < 65535) {
    $port++;
} else {
    $port--;
}
$ENV{TEST_NGINX_SERVER_SSL_PORT} = $port;
$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

env_to_nginx("PATH");
no_long_string();
run_tests();

__DATA__

=== TEST 1: read process, pattern is read line
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello world



=== TEST 2: read process, read line without line break
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "-n", "hello world"})

            local data, err, partial = proc:stdout_read_line()
            if not data then
                ngx.say(err)
                ngx.say(partial)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
closed
hello world



=== TEST 3: read process, pattern is read bytes
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            local data, err = proc:stdout_read_bytes(5)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end

            data, err = proc:stdout_read_bytes(6)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello
 world



=== TEST 4: read process, bytes length is zero
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            local data, err = proc:stdout_read_bytes(0)
            if not data then
                ngx.say(err)
            else
                ngx.say("data:", data)
            end
        }
    }
--- response_body
data:



=== TEST 5: read process, bytes length is less than zero
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            local ok, err = pcall(proc.stdout_read_bytes, proc, -1)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
bad len argument



=== TEST 6: read process, bytes length is more than data
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            local data, err = proc:stdout_read_bytes(20)
            if not data then
                ngx.say(err)
            else
                ngx.say("data:", data)
            end
        }
    }
--- response_body
closed



=== TEST 7: read process, pattern is read all
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo -n hello && sleep 0.05 && echo -n world"})

            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
helloworld



=== TEST 8: read process, pattern is read any
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo -n hello && sleep 0.05 && echo -n world"})

            -- increase timeout to ensure read_any could return before timeout
            proc:set_timeouts(5000, 5000, 5000, nil)
            local data, err = proc:stdout_read_any(1024)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end

            data, err = proc:stdout_read_any(1024)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello
world



=== TEST 9: read process, pattern is read any, with limited, max <= 0
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo -n hello && sleep 0.05 && echo -n world"})

            local ok, err = pcall(proc.stdout_read_any, proc, 0)
            if not ok then
                ngx.say(err)
            end
        }
    }
--- response_body
bad max argument



=== TEST 10: read process, pattern is read any, with limited, limit larger than read data
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo -n hello && sleep 0.05 && echo -n world"})

            local data, err = proc:stdout_read_any(1024)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end

            data, err = proc:stdout_read_any(512)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello
world



=== TEST 11: read process, pattern is read any, with limited, limit smaller than read data
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo -n hello && sleep 0.05 && echo -n world"})

            local data, err = proc:stdout_read_any(4)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end

            data, err = proc:stdout_read_any(3)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end

            data, err = proc:stdout_read_any(1024)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hell
o
world



=== TEST 12: read process, without yield
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            ngx.sleep(0.05)
            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello world



=== TEST 13: read process, without yield, get partial data
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "-n", "hello world"})

            ngx.sleep(0.05)
            local data, err, partial = proc:stdout_read_line()
            if not data then
                ngx.say(err)
                ngx.say(partial)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
closed
hello world



=== TEST 14: read process, without yield, pattern is read bytes
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            ngx.sleep(0.05)
            local data, err = proc:stdout_read_bytes(9)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
hello wor



=== TEST 15: read process, without yield, pattern is read all
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo hello && echo world"})

            ngx.sleep(0.05)
            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            else
                ngx.print(data)
            end
        }
    }
--- response_body
hello
world



=== TEST 16: read process, without yield, pattern is read any
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "echo -n hello && sleep 0.01 && echo -n world"})

            ngx.sleep(0.05)
            local data, err = proc:stdout_read_any(1024)
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }
--- response_body
helloworld



=== TEST 17: read process, without yield, read more data than preallocated buffer
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local s = ("0123"):rep(1024)
            local proc = ngx_pipe.spawn({"echo", "-n", s})

            ngx.sleep(0.05)
            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            elseif data ~= s then
                ngx.say("actual read:", data)
            else
                ngx.say("ok")
            end
        }
    }
--- response_body
ok



=== TEST 18: read process, without yield, read more partial data than preallocated buffer
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local s = ("0123"):rep(1024)
            local proc = ngx_pipe.spawn({"echo", "-n", s})

            ngx.sleep(0.05)
            local data, err, partial = proc:stdout_read_line()
            if not data then
                ngx.say(err)
                if partial ~= s then
                    ngx.say("actual read:", data)
                else
                    ngx.say("ok")
                end
            end
        }
    }
--- response_body
closed
ok



=== TEST 19: read process, with yield, read more data than preallocated buffer
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local s = ("0123"):rep(1024)
            local proc = ngx_pipe.spawn({"echo", "-n", s})

            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            elseif data ~= s then
                ngx.say("actual read:", data)
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
lua pipe read yielding



=== TEST 20: read process, with yield, read more partial data than preallocated buffer
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local s = ("0123"):rep(1024)
            local proc = ngx_pipe.spawn({"echo", "-n", s})

            local data, err, partial = proc:stdout_read_line()
            if not data then
                ngx.say(err)
                if partial ~= s then
                    ngx.say("actual read:", data)
                else
                    ngx.say("ok")
                end
            end
        }
    }
--- no_error_log
[error]
--- error_log
lua pipe read yielding
--- response_body
closed
ok



=== TEST 21: read process, mix read pattern
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local script = [[
                echo -n hello
                sleep 0.1
                echo world
                echo more
                sleep 0.1
                echo -n da
                sleep 0.1
                echo -n ta
            ]]
            local proc = ngx_pipe.spawn({"sh", "-c", script})

            local function check_call(proc, func, ...)
                local data, err = func(proc, ...)
                if not data then
                    ngx.say(err)
                    ngx.exit(ngx.OK)
                end
                ngx.say(data)
            end

            ngx.say("reading any")
            check_call(proc, proc.stdout_read_any, 1024)

            ngx.say("reading 3")
            check_call(proc, proc.stdout_read_bytes, 3)

            ngx.say("reading line")
            check_call(proc, proc.stdout_read_line)

            ngx.say("reading 2")
            check_call(proc, proc.stdout_read_bytes, 2)

            ngx.say("reading any")
            check_call(proc, proc.stdout_read_any, 1024)

            ngx.say("reading all")
            check_call(proc, proc.stdout_read_all)
        }
    }
--- response_body
reading any
hello
reading 3
wor
reading line
ld
reading 2
mo
reading any
re

reading all
data



=== TEST 22: read process, no data to read
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", 0.01})

            local data, err = proc:stdout_read_any(1024)
            if not data then
                ngx.say(err)
            else
                ngx.say("data:", data)
            end
        }
    }
--- response_body
closed



=== TEST 23: read process, no data to read, use read all
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", 0.01})

            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            else
                ngx.say("data:", data)
            end
        }
    }
--- response_body
data:



=== TEST 24: read process after waiting
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"echo", "hello world"})

            local ok, err = proc:wait()
            if not ok then
                ngx.say("wait failed: ", err)
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



=== TEST 25: more than one coroutines read a process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "sleep 0.1 && echo hello && echo world"})

            local function read()
                local data, err = proc:stdout_read_line()
                if not data then
                    ngx.say(err)
                else
                    ngx.say(data)
                end
            end

            local th1 = ngx.thread.spawn(read)
            local th2 = ngx.thread.spawn(read)
            ngx.thread.wait(th1)
            ngx.thread.wait(th2)
            ngx.thread.spawn(read)
        }
    }
--- response_body
pipe busy reading
hello
world



=== TEST 26: read process, timeout
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", "10s"})

            proc:set_timeouts(nil, 100)

            local ok, err = proc:stdout_read_line()
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
lua pipe add timer for reading: 100(ms)



=== TEST 27: read process, aborted by uthread kill
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "sleep 0.1 && echo hello"})

            local function read()
                proc:stdout_read_line()
                ngx.log(ngx.ERR, "can't reach here")
            end

            local th = ngx.thread.spawn(read)
            ngx.thread.kill(th)

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
--- no_error_log
[error]
--- error_log
lua pipe read process:
lua pipe proc read stdout cleanup



=== TEST 28: read process while waiting process in other request
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            package.loaded.proc = ngx_pipe.spawn({"sh", "-c", "sleep 0.01 && echo hello world && exit 2"})
            local res1 = ngx.location.capture("/req1")
            local res2 = ngx.location.capture("/req2")
            ngx.print(res1.body)
            ngx.print(res2.body)
        }
    }

    location = /req1 {
        content_by_lua_block {
            local data, err = package.loaded.proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }

    location = /req2 {
        content_by_lua_block {
            local ok, reason, status = package.loaded.proc:wait()
            if not ok then
                ngx.say(reason)
                ngx.say(status)
            end
        }
    }
--- response_body
hello world
exit
2



=== TEST 29: read process while waiting process in other request, return error
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            package.loaded.proc = ngx_pipe.spawn({"sh", "-c", "sleep 10s"})
            local res1, res2 = ngx.location.capture_multi{{"/req1"}, {"/req2"}}
            ngx.print(res1.body)
            ngx.print(res2.body)
        }
    }

    location = /req1 {
        content_by_lua_block {
            local proc = package.loaded.proc
            proc:set_timeouts(nil, 100)
            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
            else
                ngx.say(data)
            end
        }
    }

    location = /req2 {
        content_by_lua_block {
            local proc = package.loaded.proc
            -- sleep to ensure proc is already spawned under Valgrind
            ngx.sleep(0.2)
            os.execute("kill -TERM " .. proc:pid())
            local ok, reason, status = proc:wait()
            if not ok then
                ngx.say(reason)
                ngx.say(status)
            end
        }
    }
--- response_body
timeout
signal
15



=== TEST 30: user case with read and wait
--- no_checke_leak
--- http_config
    server {
        listen $TEST_NGINX_SERVER_SSL_PORT ssl;
        server_name test.com;
        ssl_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;
        ssl_certificate_key $TEST_NGINX_CERT_DIR/cert/test.key;
    }
--- config
    lua_ssl_trusted_certificate $TEST_NGINX_CERT_DIR/cert/test.crt;

    location /t {
        set $addr 127.0.0.1:$TEST_NGINX_SERVER_SSL_PORT;
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local addr = ngx.var.addr;
            local f, err = ngx_pipe.spawn({"sh", "-c", "echo 'Q' | openssl s_client -connect " .. addr})
            if not f then
                ngx.say(err)
                return
            end

            local out = f:stdout_read_all()
            if out:find("CONNECTED", 1, true) ~= 1 then
                ngx.say("could not find CONNECTED in output: ", out)
                local stderr_out = f:stderr_read_all()
                ngx.say("the message from stderr is: ", stderr_out)
                return
            end

            local ok, reason = f:wait()
            if not ok then
                ngx.say(reason)
            else
                ngx.say('ok')
                ngx.say(reason)
            end
        }
    }
--- response_body
ok
exit



=== TEST 31: ensure reading process in phases without yield support is disabled
--- http_config
    init_worker_by_lua_block {
        local ngx_pipe = require "ngx.pipe"
        local proc = ngx_pipe.spawn({"echo", "hello world"})

        local ok, err = pcall(proc.stdout_read_line, proc)
        if not ok then
            package.loaded.res = err
        end
    }
--- config
    location = /t {
        content_by_lua_block {
            ngx.say(package.loaded.res)
        }
    }
--- response_body_like
.+ API disabled in the context of init_worker_by_lua\*



=== TEST 32: but we could spawn it in init_worker_by_lua and read it later
--- http_config
    init_worker_by_lua_block {
        local ngx_pipe = require "ngx.pipe"
        local proc = ngx_pipe.spawn({"echo", "hello world"})
        package.loaded.proc = proc
    }

--- config
    location = /t {
        content_by_lua_block {
            local proc = package.loaded.proc

            if proc then
                local data, err = proc:stdout_read_line()
                if not data then
                    ngx.say(err)
                else
                    ngx.say(data)
                end

                -- we could only read once as we only spawn the proess once
                package.loaded.proc = nil

            else

                -- so just return the expected data in repeated tests.
                ngx.say("closed")
            end
        }
    }
--- response_body
closed



=== TEST 33: read process, aborted by uthread kill, with graceful shutdown
--- user_files
>>> a.lua
local ngx_pipe = require "ngx.pipe"
local proc = ngx_pipe.spawn({"bash"})

local function func()
    proc:stdout_read_line()
    ngx.log(ngx.ERR, "can't reach here")
end

local th = ngx.thread.spawn(func)
ngx.thread.kill(th)

local data, err = proc:kill(9) -- SIGKILL
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
            proc:set_timeouts(100, 100, 100, 100)

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



=== TEST 34: spawn process with stdout_read_timeout option
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sleep", "10s"}, {
                stdout_read_timeout = 100
            })

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say("stdout err: ", err)
            else
                ngx.say("stdout: ", data)
            end
        }
    }
--- response_body
stdout err: timeout
--- error_log
lua pipe add timer for reading: 100(ms)
--- no_error_log
[error]



=== TEST 35: start a daemon process
--- config
    location = /t {
        content_by_lua_block {
            local ngx_pipe = require "ngx.pipe"
            local proc = ngx_pipe.spawn({"sh", "-c", "daemonize /usr/bin/sleep 30 >/dev/null 2>&1"})

            local data, err = proc:stdout_read_all()
            if not data then
                ngx.say(err)
            end

            ngx.say("OK")
        }
    }
--- response_body
OK
--- no_error_log
[error]
