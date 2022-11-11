# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
log_level('error');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 15);

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
});

#no_diff();
no_long_string();
#check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
            ngx.log(ngx.ERR, "enter 1")
            ngx.log(ngx.ERR, "enter 11")

            local errlog = require "ngx.errlog"
            local res, err = errlog.get_logs()
            if not res then
                error("FAILED " .. err)
            end
            ngx.say("log lines:", #res / 3)
        }
    }
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            ngx.log(ngx.ERR, "enter 1")
            ngx.log(ngx.ERR, "enter 22" .. string.rep("a", 4096))

            local errlog = require "ngx.errlog"
            local res, err = errlog.get_logs()
            if not res then
                error("FAILED " .. err)
            end
            ngx.say("log lines:", #res / 3)
        }
    }
--- request
GET /t
--- response_body
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



=== TEST 3: 404 error (not found)
--- http_config
    lua_capture_error_log 4m;
--- config
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)
    }
--- request
GET /t
--- error_code: 404
--- grep_error_log eval
qr/capture log line:\d+|No such file or directory/
--- grep_error_log_out eval
[
qr/^No such file or directory
capture log line:1
$/,
qr/^No such file or directory
capture log line:2
$/
]
--- skip_nginx: 2: <1.11.2



=== TEST 4: 500 error
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        content_by_lua_block {
            local t = {}/4
        }
    }
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)
    }
--- request
GET /t
--- error_code: 500
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
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        echo "hello";
    }
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)
    }
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 4m;
    error_log logs/error_http.log error;
--- config
    location /t {
        error_log logs/error.log error;
        access_by_lua_block {
            ngx.log(ngx.ERR, "enter access /t")
        }
        echo "hello";
    }
    log_by_lua_block {
        local errlog = require "ngx.errlog"
        local res, err = errlog.get_logs()
        if not res then
            error("FAILED " .. err)
        end
        ngx.log(ngx.ERR, "capture log line:", #res / 3)

    }
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 3k;
--- config
    location /t {
        echo "hello";
    }
--- must_die
--- error_log
invalid capture error log size "3k", minimum size is 4096
--- skip_nginx: 2: <1.11.2



=== TEST 8: invalid size (no argu)
--- http_config
    lua_capture_error_log;
--- config
    location /t {
        echo "hello";
    }
--- must_die
--- error_log
invalid number of arguments in "lua_capture_error_log" directive
--- skip_nginx: 2: <1.11.2



=== TEST 9: without directive + ngx.errlog
--- config
    location /t {
        access_by_lua_block {
            ngx.log(ngx.ERR, "enter 1")

            local errlog = require "ngx.errlog"
            local res, err = errlog.get_logs()
            if not res then
                error("FAILED " .. err)
            end
            ngx.say("log lines:", #res / 3)
        }
    }
--- request
GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log
directive "lua_capture_error_log" is not set
--- skip_nginx: 3: <1.11.2



=== TEST 10: without directive + ngx.set_filter_level
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.ERR)
            if not status then
                error(err)
            end
        }
    }
--- request
GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log
directive "lua_capture_error_log" is not set
--- skip_nginx: 3: <1.11.2



=== TEST 11: filter log by level(ngx.INFO)
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.INFO)
            if not status then
                error(err)
            end

            ngx.log(ngx.INFO, "-->1")
            ngx.log(ngx.WARN, "-->2")
            ngx.log(ngx.ERR, "-->3")
        }
        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local res = errlog.get_logs()
            ngx.say("log lines:", #res / 3)
        }
    }
--- log_level: info
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            ngx.log(ngx.INFO, "-->1")
            ngx.log(ngx.WARN, "-->2")
            ngx.log(ngx.ERR, "-->3")
        }
        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local res = errlog.get_logs()
            ngx.say("log lines:", #res / 3)
        }
    }
--- log_level: info
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 4m;
--- log_level: info
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.CRIT)
            if not status then
                error(err)
            end

            ngx.log(ngx.INFO, "-->1")
            ngx.log(ngx.WARN, "-->2")
            ngx.log(ngx.ERR, "-->3")
        }
        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local res = errlog.get_logs()
            ngx.say("log lines:", #res / 3)
        }
    }
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
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
    }
--- request
GET /t
--- response_body
log lines:2
log lines:1
--- skip_nginx: 2: <1.11.2



=== TEST 15: wrong argument
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level()
            if not status then
                error(err)
            end
        }
    }
--- request
GET /t
--- error_code: 500
--- response_body_like: 500
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
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            ngx.log(ngx.INFO, "-->1")
            ngx.log(ngx.WARN, "-->2")
            ngx.log(ngx.ERR, "-->3")
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local res = errlog.get_logs()
            for i = 1, #res, 3 do
                ngx.say("log level:", res[i])
                ngx.say("log body:",  res[i + 2])
            end
        }
    }
--- log_level: info
--- request
GET /t
--- response_body_like
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: -->2, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: -->3, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
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
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            for i = 1, 100 do
                ngx.log(ngx.INFO, "--> ", i)
                ngx.log(ngx.WARN, "--> ", i)
                ngx.log(ngx.ERR, "--> ", i)
            end
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
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
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
\A(?:log lines: #21
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 90, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 91, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 99, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
|log lines: #20
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 91, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 91, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 92, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 99, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
)\z
--- skip_nginx: 2: <1.11.2
--- wait: 0.1



=== TEST 18: flood the capturing buffer (5k)
--- http_config
    lua_capture_error_log 5k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            for i = 1, 100 do
                ngx.log(ngx.INFO, "--> ", i)
                ngx.log(ngx.WARN, "--> ", i)
                ngx.log(ngx.ERR, "--> ", i)
            end
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
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
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
\Alog lines: #26
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 89, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 99, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
\z
--- skip_nginx: 2: <1.11.2



=== TEST 19: fetch a few and generate a few, then fetch again (overflown again)
--- http_config
    lua_capture_error_log 5k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            for i = 1, 100 do
                ngx.log(ngx.INFO, "--> ", i)
                ngx.log(ngx.WARN, "--> ", i)
                ngx.log(ngx.ERR, "--> ", i)
            end
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"

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
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
\Amsg count: 3
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 89, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
msg count: 3
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 90, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 90, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 91, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 102, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 103, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: --> 104, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
\z
--- skip_nginx: 2: <1.11.2



=== TEST 20: fetch a few and generate a few, then fetch again (not overflown again)
--- http_config
    lua_capture_error_log 5k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            for i = 1, 100 do
                ngx.log(ngx.INFO, "--> ", i)
                ngx.log(ngx.WARN, "--> ", i)
                ngx.log(ngx.ERR, "--> ", i)
            end
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"

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
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
\Amsg count: 3
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 88, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 89, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
msg count: 3
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 89, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:5
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[warn\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 90, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 90, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: --> 100, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: howdy, something new!, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: howdy, something even newer!, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
\z
--- skip_nginx: 2: <1.11.2



=== TEST 21: multi-line error log
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            ngx.log(ngx.ERR, "-->\n", "new line")
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local res = errlog.get_logs()
            ngx.say("log lines: #", #res / 3)

            for i = 1, #res, 3 do
                ngx.say("log level:", res[i])
                ngx.say("log body:",  res[i + 2])
            end
        }
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
\Alog lines: #1
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: -->
new line, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
\z
--- skip_nginx: 2: <1.11.2



=== TEST 22: user-supplied Lua table to hold the result (get one log + no log)
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local status, err = errlog.set_filter_level(ngx.WARN)
            if not status then
                error(err)
            end

            ngx.log(ngx.ERR, "-->\n", "new line")
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
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
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
\Amaybe log lines: #1
log level:4
log body:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*access_by_lua\(nginx.conf:\d+\):\d+: -->
new line, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
end
maybe log lines: #1
end
\z
--- skip_nginx: 2: <1.11.2



=== TEST 23: the system default filter level is "debug"
--- config
    location /t {
        content_by_lua_block {
            local errlog = require "ngx.errlog"
            ngx.print('Is "debug" the system default filter level? ',
                      errlog.get_sys_filter_level() == ngx.DEBUG)
        }
    }
--- log_level: debug
--- request
GET /t
--- response_body chomp
Is "debug" the system default filter level? true



=== TEST 24: the system default filter level is "emerg"
--- config
    location /t {
        content_by_lua_block {
            local errlog = require "ngx.errlog"
            ngx.print('Is "emerg" the system default filter level? ',
                      errlog.get_sys_filter_level() == ngx.EMERG)
        }
    }
--- log_level: emerg
--- request
GET /t
--- response_body chomp
Is "emerg" the system default filter level? true



=== TEST 25: get system default filter level during Nginx starts (init)
--- init_by_lua_block
    local errlog = require "ngx.errlog"
    package.loaded.log_level = errlog.get_sys_filter_level()

--- config
    location /t {
        content_by_lua_block {
            local log_level = package.loaded.log_level

            if log_level >= ngx.WARN then
                ngx.log(ngx.WARN, "log a warning event")
            else
                ngx.log(ngx.WARN, "do not log another warning event")
            end
        }
    }
--- log_level: warn
--- request
GET /t
--- error_log
log a warning event
--- no_error_log
do not log another warning event



=== TEST 26: get system default filter level during Nginx worker starts (init worker)
--- http_config
    init_worker_by_lua_block {
        local errlog = require "ngx.errlog"
        package.loaded.log_level = errlog.get_sys_filter_level()
    }
--- config
    location /t {
        content_by_lua_block {
            local log_level = package.loaded.log_level

            if log_level >= ngx.WARN then
                ngx.log(ngx.WARN, "log a warning event")
            else
                ngx.log(ngx.WARN, "do not log another warning event")
            end
        }
    }
--- log_level: warn
--- request
GET /t
--- error_log
log a warning event
--- no_error_log
do not log another warning event



=== TEST 27: sanity (with log time)
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
            ngx.log(ngx.ERR, "enter 1")
            ngx.log(ngx.ERR, "enter 11")

            local errlog = require "ngx.errlog"
            local res, err = errlog.get_logs(nil, nil, {fetch_time = true})
            if not res then
                error("FAILED " .. err)
            end
            ngx.say("log lines:", #res / 3)
        }
    }
--- request
GET /t
--- response_body
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
--- http_config
    lua_capture_error_log 4m;
--- config
    location /t {
        access_by_lua_block {
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
    }
--- request
GET /t
--- response_body_like chomp
\Alog lines: 2
log level: 3
log time: \d+(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[crit\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: enter 1, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
same with now: true
log level: 4
log time: \d{10}(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?access_by_lua\(nginx.conf:\d+\):\d+: enter 11, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
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
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local msg = string.rep("*", 10)

            for i = 1, 2 do
                ngx.log(ngx.ERR, msg .. i)
            end
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local msg = string.rep("*", 10)

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
    }
--- log_level: info
--- request
GET /t
--- response_body_like chomp
log level: 4
log time: \d+(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: \*\*\*\*\*\*\*\*\*\*39, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
log level: 4
log time: \d{10}(?:\.\d+)?
log body: \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[error\] (\d+).*?content_by_lua\(nginx.conf:\d+\):\d+: \*\*\*\*\*\*\*\*\*\*40, client: 127.0.0.1, server: localhost, request: "GET /t HTTP/1.1", host: "localhost"
--- skip_nginx: 2: <1.11.2



=== TEST 30: ringbuf sentinel bug1
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local msg = string.rep("a", 20)
            local bigmsg = string.rep("A", 3000)

            for i = 1, 10 do
                ngx.log(ngx.ERR, msg)
            end
            ngx.log(ngx.ERR, bigmsg)
            ngx.log(ngx.ERR, msg)
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"

            local res = errlog.get_logs(2)
            ngx.say("log lines: #", #res / 3)

            for i = 1, #res, 3 do
                ngx.say(string.gsub(res[i + 2], "^.*([Aa][Aa][Aa]).*$", "%1"), "")
            end
        }
    }
--- log_level: info
--- request
GET /t
--- response_body
log lines: #2
AAA
aaa
--- skip_nginx: 2: <1.11.2



=== TEST 31: ringbuf sentinel bug2
--- http_config
    lua_capture_error_log 4k;
--- config
    location /t {
        access_by_lua_block {
            local errlog = require "ngx.errlog"
            local msg = string.rep("a", 20)

            for i = 1, 20 do
                ngx.log(ngx.ERR, msg)
            end
        }

        content_by_lua_block {
            local errlog = require "ngx.errlog"
            local msg = string.rep("a", 20)

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
    }
--- log_level: info
--- request
GET /t
--- response_body
log lines: #18
log lines: #8
--- skip_nginx: 2: <1.11.2
