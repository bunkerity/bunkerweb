# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('error');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 10);

add_block_preprocessor(sub {
    my $block = shift;

    my $stream_config = $block->stream_config || '';

    $stream_config .= <<_EOC_;
    lua_package_path '$t::TestCore::Stream::lua_package_path';
    init_by_lua_block {
        $t::TestCore::Stream::init_by_lua_block
        $init_by_lua_block
    }
_EOC_

    $block->set_value("stream_config", $stream_config);
});

#no_diff();
no_long_string();
#check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
        content_by_lua_block {
            ngx.log(ngx.ERR, "enter 1")
            ngx.log(ngx.ERR, "enter 11")

            local errlog = require "ngx.errlog"
            local res, err = errlog.get_logs()
            if not res then
                error("FAILED " .. err)
            end
            ngx.say("log lines:", #res / 3)
        }
--- stream_response
log lines:2
--- grep_error_log eval
qr/enter \d+/
--- grep_error_log_out eval
[
"enter 1
enter 11
",
"enter 1
enter 11
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 2: overflow captured error logs
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.ERR, "enter 1")
        ngx.log(ngx.ERR, "enter 22" .. string.rep("a", 4096))

        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.say("log lines:", #res / 3)
    }
--- stream_response
log lines:1
--- grep_error_log eval
qr/enter \d+/
--- grep_error_log_out eval
[
"enter 1
enter 22
",
"enter 1
enter 22
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 3: client connected info
--- log_level: info
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)
    }
--- grep_error_log eval
qr/capture log line:\d+|client .*? connected to .*?/
--- grep_error_log_out eval
[
qr/^client .*? connected to .*?
capture log line:1
$/,
qr/^client .*? connected to .*?
capture log line:2
$/
]
--- skip_nginx: 2: <1.11.2



=== TEST 4: 500 error
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local t = {}/4
    }
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)
    }
--- grep_error_log eval
qr/capture log line:\d+|attempt to perform arithmetic on a table value/
--- grep_error_log_out eval
[
qr/^attempt to perform arithmetic on a table value
capture log line:1
$/,
qr/^attempt to perform arithmetic on a table value
capture log line:2
$/
]
--- skip_nginx: 2: <1.11.2



=== TEST 5: no error log
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        ngx.say("hello")
    }
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)
    }
--- stream_response
hello
--- grep_error_log eval
qr/capture log line:\d+/
--- grep_error_log_out eval
[
qr/^capture log line:0
$/,
qr/^capture log line:1
$/
]
--- skip_nginx: 3: <1.11.2



=== TEST 6: customize the log path
--- stream_config
    lua_capture_error_log 4m;
    error_log logs/error_stream.log error;
--- stream_server_config
    error_log logs/error.log error;
    content_by_lua_block {
        ngx.log(ngx.ERR, "enter access /t")
        ngx.say("hello")
    }
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)

    }
--- stream_response
hello
--- grep_error_log eval
qr/capture log line:\d+|enter access/
--- grep_error_log_out eval
[
qr/^enter access
capture log line:1
$/,
qr/^enter access
capture log line:2
$/
]
--- skip_nginx: 3: <1.11.2



=== TEST 7: invalid size (< 4k)
--- stream_config
    lua_capture_error_log 3k;
--- stream_server_config
    content_by_lua_block {
        ngx.say("hello")
    }
--- must_die
--- error_log
invalid capture error log size "3k", minimum size is 4096
--- skip_nginx: 2: <1.11.2



=== TEST 8: invalid size (no argu)
--- stream_config
    lua_capture_error_log;
--- stream_server_config
    content_by_lua_block {
        ngx.say("hello")
    }
--- must_die
--- error_log
invalid number of arguments in "lua_capture_error_log" directive
--- skip_nginx: 2: <1.11.2



=== TEST 9: without directive + ngx.errlog
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.ERR, "enter 1")

        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.say("log lines:", #res / 3)
    }
--- error_log
directive "lua_capture_error_log" is not set
--- skip_nginx: 3: <1.11.2



=== TEST 10: without directive + ngx.set_filter_level
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.ERR)
        if not status then
            error(err)
        end
    }
--- error_log
directive "lua_capture_error_log" is not set
--- skip_nginx: 3: <1.11.2



=== TEST 11: filter log by level(ngx.INFO)
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.INFO)
        if not status then
            error(err)
        end

        ngx.log(ngx.NOTICE, "-->1")
        ngx.log(ngx.WARN, "-->2")
        ngx.log(ngx.ERR, "-->3")

        local res = errlog.get_logs()
        ngx.say("log lines:", #res / 3)
    }
--- log_level: notice
--- stream_response
log lines:3
--- grep_error_log eval
qr/-->\d+/
--- grep_error_log_out eval
[
"-->1
-->2
-->3
",
"-->1
-->2
-->3
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 12: filter log by level(ngx.WARN)
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        ngx.log(ngx.NOTICE, "-->1")
        ngx.log(ngx.WARN, "-->2")
        ngx.log(ngx.ERR, "-->3")

        local res = errlog.get_logs()
        ngx.say("log lines:", #res / 3)
    }
--- log_level: notice
--- stream_response
log lines:2
--- grep_error_log eval
qr/-->\d+/
--- grep_error_log_out eval
[
"-->1
-->2
-->3
",
"-->1
-->2
-->3
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 13: filter log by level(ngx.CRIT)
--- stream_config
    lua_capture_error_log 4m;
--- log_level: notice
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.CRIT)
        if not status then
            error(err)
        end

        ngx.log(ngx.NOTICE, "-->1")
        ngx.log(ngx.WARN, "-->2")
        ngx.log(ngx.ERR, "-->3")

        local res = errlog.get_logs()
        ngx.say("log lines:", #res / 3)
    }
--- stream_response
log lines:0
--- grep_error_log eval
qr/-->\d+/
--- grep_error_log_out eval
[
"-->1
-->2
-->3
",
"-->1
-->2
-->3
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 14: set max count and reuse table
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        tab_clear = require "table.clear"
        ngx.log(ngx.ERR, "enter 1")
        ngx.log(ngx.ERR, "enter 22")
        ngx.log(ngx.ERR, "enter 333")

        local errlog = require "ngx.errlog"
        local res = {}
        local err
        res, err = errlog.get_logs(2, res)
        if not res then
            error("FAILED " .. err)
        end
        ngx.say("log lines:", #res / 3)

        tab_clear(res)
        res, err = errlog.get_logs(2, res)
        if not res then
            error("FAILED " .. err)
        end
        ngx.say("log lines:", #res / 3)
    }
--- stream_response
log lines:2
log lines:1
--- skip_nginx: 2: <1.11.2



=== TEST 15: wrong argument
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level()
        if not status then
            error(err)
        end
    }
--- grep_error_log eval
qr/missing \"level\" argument/
--- grep_error_log_out eval
[
"missing \"level\" argument
",
"missing \"level\" argument
",
]
--- skip_nginx: 3: <1.11.2



=== TEST 16: check the captured error log body
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        ngx.log(ngx.NOTICE, "-->1")
        ngx.log(ngx.WARN, "-->2")
        ngx.log(ngx.ERR, "-->3")

        local res = errlog.get_logs()
        for i = 1, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: -->2, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: -->3, client: 127.0.0.1, server: 0.0.0.0:\d+
--- grep_error_log eval
qr/-->\d+/
--- grep_error_log_out eval
[
"-->1
-->2
-->3
",
"-->1
-->2
-->3
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 17: flood the capturing buffer (4k)
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        for i = 1, 100 do
            ngx.log(ngx.NOTICE, "--> ", i)
            ngx.log(ngx.WARN, "--> ", i)
            ngx.log(ngx.ERR, "--> ", i)
        end

        local res = errlog.get_logs(1000)
        ngx.say("log lines: #", #res / 3)

        -- first 3 logs
        for i = 1, 3 * 3, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:", res[i + 2])
        end

        -- last 3 logs
        for i = #res - 8, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:", res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like chomp
\A(?:log lines: #26
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 89, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 99, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: 0.0.0.0:\d+
)\z
--- skip_nginx: 2: <1.11.2
--- wait: 0.1



=== TEST 18: flood the capturing buffer (5k)
--- stream_config
    lua_capture_error_log 5k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        for i = 1, 100 do
            ngx.log(ngx.NOTICE, "--> ", i)
            ngx.log(ngx.WARN, "--> ", i)
            ngx.log(ngx.ERR, "--> ", i)
        end

        local res = errlog.get_logs(1000)
        ngx.say("log lines: #", #res / 3)

        -- first 3 logs
        for i = 1, 3 * 3, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:", res[i + 2])
        end

        -- last 3 logs
        for i = #res - 8, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:", res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like chomp
\A(?:log lines: #33
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 84, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 99, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: 0.0.0.0:\d+
)\z
--- skip_nginx: 2: <1.11.2
--- wait: 0.1



=== TEST 19: fetch a few and generate a few, then fetch again (overflown again)
--- stream_config
    lua_capture_error_log 5k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        for i = 1, 100 do
            ngx.log(ngx.NOTICE, "--> ", i)
            ngx.log(ngx.WARN, "--> ", i)
            ngx.log(ngx.ERR, "--> ", i)
        end

        local res = errlog.get_logs(3)
        ngx.say("msg count: ", #res / 3)

        -- first 3 logs
        for i = 1, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end

        ngx.log(ngx.ERR, "--> 101")
        ngx.log(ngx.ERR, "--> 102")
        ngx.log(ngx.ERR, "--> 103")
        ngx.log(ngx.ERR, "--> 104")

        local res = errlog.get_logs(3)
        ngx.say("msg count: ", #res / 3)

        -- first 3 logs
        for i = 1, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end

        local res = errlog.get_logs(1000)
        -- last 3 logs
        for i = #res - 8, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like chomp
\Amsg count: 3
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 84, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
msg count: 3
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 86, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 86, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 87, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 102, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 103, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 104, client: 127.0.0.1, server: 0.0.0.0:\d+
|msg count: 3
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 84, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
msg count: 3
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 87, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 87, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 102, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 103, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 104, client: 127.0.0.1, server: 0.0.0.0:\d+
\z
--- skip_nginx: 2: <1.11.2



=== TEST 20: fetch a few and generate a few, then fetch again (not overflown again)
--- stream_config
    lua_capture_error_log 5k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        for i = 1, 100 do
            ngx.log(ngx.NOTICE, "--> ", i)
            ngx.log(ngx.WARN, "--> ", i)
            ngx.log(ngx.ERR, "--> ", i)
        end

        local res = errlog.get_logs(3)
        ngx.say("msg count: ", #res / 3)

        -- first 3 logs
        for i = 1, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end

        ngx.log(ngx.ERR, "howdy, something new!")
        ngx.log(ngx.ERR, "howdy, something even newer!")

        local res = errlog.get_logs(3)
        ngx.say("msg count: ", #res / 3)

        -- first 3 logs
        for i = 1, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end

        local res = errlog.get_logs(1000)
        -- last 3 logs
        for i = #res - 8, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like chomp
\Amsg count: 3
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 84, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 85, client: 127.0.0.1, server: 0.0.0.0:\d+
msg count: 3
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 86, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 86, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 87, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: howdy, something new!, client: 127.0.0.1, server: 0.0.0.0:\d+
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: howdy, something even newer!, client: 127.0.0.1, server: 0.0.0.0:\d+
\z
--- skip_nginx: 2: <1.11.2



=== TEST 21: multi-line error log
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        ngx.log(ngx.ERR, "-->\n", "new line")

        local res = errlog.get_logs()
        ngx.say("log lines: #", #res / 3)

        for i = 1, #res, 3 do
            ngx.say("log level:", res[i])
            ngx.say("log body:",  res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like chomp
\Alog lines: #1
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: -->
new line, client: 127.0.0.1, server: 0.0.0.0:\d+
\z
--- skip_nginx: 2: <1.11.2



=== TEST 22: user-supplied Lua table to hold the result (get one log + no log)
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            error(err)
        end

        ngx.log(ngx.ERR, "-->\n", "new line")

        local t = {}

        for i = 1, 2 do
            local res = errlog.get_logs(10, t)
            ngx.say("maybe log lines: #", #res / 3)
            for j = 1, #res, 3 do
                local level, msg = res[j], res[j + 2]
                if not level then
                    break
                end
                ngx.say("log level:", level)
                ngx.say("log body:",  msg)
            end
            ngx.say("end")
        end
    }
--- log_level: notice
--- stream_response_like chomp
\Amaybe log lines: #1
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*content_by_lua\(nginx.conf:\d+\):\d+: -->
new line, client: 127.0.0.1, server: 0.0.0.0:\d+
end
maybe log lines: #1
end
\z
--- skip_nginx: 2: <1.11.2



=== TEST 23: the system default filter level is "debug"
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        ngx.print('Is "debug" the system default filter level? ',
                  errlog.get_sys_filter_level() == ngx.DEBUG)
    }
--- log_level: debug
--- stream_response chomp
Is "debug" the system default filter level? true



=== TEST 24: the system default filter level is "emerg"
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        ngx.print('Is "emerg" the system default filter level? ',
                  errlog.get_sys_filter_level() == ngx.EMERG)
    }
--- log_level: emerg
--- stream_response chomp
Is "emerg" the system default filter level? true



=== TEST 25: get system default filter level during Nginx starts (init)
--- SKIP
--- init_by_lua_block
    require "resty.core"
    local errlog = require "ngx.errlog"
    package.loaded.log_level = errlog.get_sys_filter_level()

--- stream_server_config
    content_by_lua_block {
        local log_level = package.loaded.log_level

        if log_level >= ngx.WARN then
            ngx.log(ngx.WARN, "log a warning event")
        else
            ngx.log(ngx.WARN, "do not log another warning event")
        end
    }
--- log_level: warn
--- error_log
log a warning event
--- no_error_log
do not log another warning event



=== TEST 26: get system default filter level during Nginx worker starts (init worker)
--- SKIP
--- stream_config
    init_worker_by_lua_block {
        local errlog = require "ngx.errlog"
        package.loaded.log_level = errlog.get_sys_filter_level()
    }
--- stream_server_config
    content_by_lua_block {
        local log_level = package.loaded.log_level

        if log_level >= ngx.WARN then
            ngx.log(ngx.WARN, "log a warning event")
        else
            ngx.log(ngx.WARN, "do not log another warning event")
        end
    }
--- log_level: warn
--- error_log
log a warning event
--- no_error_log
do not log another warning event



=== TEST 27: sanity (with log time)
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        ngx.log(ngx.ERR, "enter 1")
        ngx.log(ngx.ERR, "enter 11")

        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs(nil, nil, {fetch_time = true})
        if not res then
            error("FAILED " .. err)
        end
        ngx.say("log lines:", #res / 3)
    }
--- stream_response
log lines:2
--- grep_error_log eval
qr/enter \d+/
--- grep_error_log_out eval
[
"enter 1
enter 11
",
"enter 1
enter 11
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 28: log time eq ngx.now
--- stream_config
    lua_capture_error_log 4m;
--- stream_server_config
    content_by_lua_block {
        local now = ngx.now()
        ngx.log(ngx.CRIT, "enter 1")
        ngx.log(ngx.ERR, "enter 11")

        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs(nil, nil, {fetch_time = true})
        if not res then
            error("FAILED " .. err)
        end
        ngx.say("log lines: ", #res / 3)

        for i = 1, #res, 3 do
            ngx.say("log level: ", res[i])
            ngx.say("log time: ",  res[i + 1])
            ngx.say("log body: ",  res[i + 2])
            ngx.say("same with now: ",  res[i + 1] == now)
        end
    }
--- stream_response_like chomp
\Alog lines: 2
log level: 3
log time: \d+(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[crit\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: enter 1, client: 127.0.0.1, server: 0.0.0.0:\d+
same with now: true
log level: 4
log time: \d{10}(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: enter 11, client: 127.0.0.1, server: 0.0.0.0:\d+
same with now: true
--- grep_error_log eval
qr/enter \d+/
--- grep_error_log_out eval
[
"enter 1
enter 11
",
"enter 1
enter 11
"
]
--- skip_nginx: 3: <1.11.2



=== TEST 29: ringbuf overflow bug
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local msg = string.rep("*", 10)

        for i = 1, 2 do
            ngx.log(ngx.ERR, msg .. i)
        end

        for i = 1, 40 do
            local res = errlog.get_logs(1)
            if res and #res then
                ngx.log(ngx.ERR, msg .. i)
            end
        end

        local res = errlog.get_logs()
        for i = 1, #res, 3 do
            ngx.say("log level: ", res[i])
            ngx.say("log time: ",  res[i + 1])
            ngx.say("log body: ",  res[i + 2])
        end
    }
--- log_level: notice
--- stream_response_like chomp
log level: 4
log time: \d+(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: \*\*\*\*\*\*\*\*\*\*39, client: 127.0.0.1, server: 0.0.0.0:\d+
log level: 4
log time: \d{10}(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: \*\*\*\*\*\*\*\*\*\*40, client: 127.0.0.1, server: 0.0.0.0:\d+
--- skip_nginx: 2: <1.11.2



=== TEST 30: ringbuf sentinel bug1
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local msg = string.rep("a", 20)
        local bigmsg = string.rep("A", 3000)

        for i = 1, 10 do
            ngx.log(ngx.ERR, msg)
        end
        ngx.log(ngx.ERR, bigmsg)
        ngx.log(ngx.ERR, msg)

        local res = errlog.get_logs(2)
        ngx.say("log lines: #", #res / 3)

        for i = 1, #res, 3 do
            ngx.say(string.gsub(res[i + 2], "^.*([Aa][Aa][Aa]).*$", "%1"), "")
        end
    }
--- log_level: notice
--- stream_response
log lines: #2
AAA
aaa
--- skip_nginx: 2: <1.11.2



=== TEST 31: ringbuf sentinel bug2
--- stream_config
    lua_capture_error_log 4k;
--- stream_server_config
    content_by_lua_block {
        local errlog = require "ngx.errlog"
        local msg = string.rep("a", 20)

        for i = 1, 20 do
            ngx.log(ngx.ERR, msg)
        end

        local res = errlog.get_logs(18)
        ngx.say("log lines: #", #res / 3)
        ngx.flush(true)

        for i = 1, 18 do
            ngx.log(ngx.ERR, msg)
        end

        local bigmsg = string.rep("A", 2000)
        ngx.log(ngx.ERR, bigmsg)

        local res = errlog.get_logs()
        ngx.say("log lines: #", #res / 3)
        ngx.flush(true)
    }
--- log_level: notice
--- stream_response_like chomp
\A(?:log lines: #18
log lines: #1
|log lines: #18
log lines: #2
)\z
--- skip_nginx: 2: <1.11.2
