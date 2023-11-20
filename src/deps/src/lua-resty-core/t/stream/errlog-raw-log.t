# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

log_level('error');

repeat_each(1);

plan tests => repeat_each() * (blocks() * 2 + 5);

add_block_preprocessor(sub {
    my $block = shift;

    my $stream_config = $block->stream_config || '';
    my $init_by_lua_block = $block->init_by_lua_block || '';

    $stream_config .= <<_EOC_;
    lua_package_path '$t::TestCore::Stream::lua_package_path';
    init_by_lua_block {
        $t::TestCore::Stream::init_by_lua_block
        $init_by_lua_block
    }
_EOC_

    $block->set_value("stream_config", $stream_config);
});

no_long_string();
run_tests();

__DATA__

=== TEST 1: errlog.raw_log with bad log level (ngx.ERROR, -1)
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"

        local pok, err = pcall(errlog.raw_log, ngx.ERROR, "hello, log")
        if not pok then
            ngx.say("not ok: ", err)
            return
        end

        ngx.say("ok")
    }
--- stream_response
not ok: bad log level
--- no_error_log
[error]



=== TEST 2: errlog.raw_log with bad levels (9)
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"

        local pok, err = pcall(errlog.raw_log, 9, "hello, log")
        if not pok then
            ngx.say("not ok: ", err)
            return
        end

        ngx.say("ok")
    }
--- stream_response
not ok: bad log level
--- no_error_log
[error]



=== TEST 3: errlog.raw_log with bad log message
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"

        local pok, err = pcall(errlog.raw_log, ngx.ERR, 123)
        if not pok then
            ngx.say("not ok: ", err)
            return
        end

        ngx.say("ok")
    }
--- stream_response
not ok: bad argument #2 to 'raw_log' (must be a string)
--- no_error_log
[error]



=== TEST 4: errlog.raw_log test log-level ERR
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"

        errlog.raw_log(ngx.ERR, "hello world")
    }
--- error_log eval
qr/\[error\] \S+: \S+ hello world/



=== TEST 5: errlog.raw_log JITs
--- init_by_lua_block
    -- local verbose = true
    local verbose = false
    local outfile = errlog_file
    -- local outfile = "/tmp/v.log"
    if verbose then
        local dump = require "jit.dump"
        dump.on(nil, outfile)
    else
        local v = require "jit.v"
        v.on(outfile)
    end

    require "resty.core"
    -- jit.opt.start("hotloop=1")
    -- jit.opt.start("loopunroll=1000000")
    -- jit.off()
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"

        for i = 1, 100 do
            errlog.raw_log(ngx.ERR, "hello world")
        end
    }
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx.conf:\d+\):4 loop\]/



=== TEST 6: errlog.raw_log in init_by_lua
--- init_by_lua_block
    local errlog = require "ngx.errlog"
    errlog.raw_log(ngx.ERR, "hello world from init_by_lua")
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }
--- grep_error_log chop
hello world from init_by_lua
--- grep_error_log_out eval
["hello world from init_by_lua\n", ""]



=== TEST 7: errlog.raw_log in init_worker_by_lua
--- stream_config
    init_worker_by_lua_block {
        local errlog = require "ngx.errlog"
        errlog.raw_log(ngx.ERR, "hello world from init_worker_by_lua")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }
--- grep_error_log chop
hello world from init_worker_by_lua
--- grep_error_log_out eval
["hello world from init_worker_by_lua\n", ""]



=== TEST 8: errlog.raw_log with \0 in the log message
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        errlog.raw_log(ngx.ERR, "hello\0world")
        ngx.say("ok")
    }
--- stream_response
ok
--- error_log eval
"hello\0world, client: "



=== TEST 9: errlog.raw_log is captured by errlog.get_logs()
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        errlog.raw_log(ngx.ERR, "hello from raw_log()")

        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end

        ngx.say("log lines: ", #res / 3)
    }
--- stream_response
log lines: 1
--- error_log eval
qr/\[error\] .*? hello from raw_log\(\)/
--- skip_nginx: 3: <1.11.2
