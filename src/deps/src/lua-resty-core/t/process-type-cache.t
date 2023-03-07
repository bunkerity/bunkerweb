# vim:set ft= ts=4 sw=4 et fdm=marker:

BEGIN {
    undef $ENV{TEST_NGINX_USE_STAP};
}

use lib '.';
use t::TestCore;

#worker_connections(1014);
master_on();
#log_level('info');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5);

our $HttpConfig = <<_EOC_;
    proxy_cache_path /tmp/proxy_cache_dir keys_zone=cache_one:200m;

    $t::TestCore::HttpConfig

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local v
        local typ = (require "ngx.process").type
        for i = 1, 400 do
            v = typ()
        end

        if v == "helper" then
            ngx.log(ngx.WARN, "process type: ", v)
        end
    }
_EOC_

#no_diff();
#no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- http_config eval: $::HttpConfig
--- config
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.1)
            local v
            local typ = (require "ngx.process").type
            for i = 1, 200 do
                v = typ()
            end
            ngx.say("type: ", v)
        }
    }
--- request
GET /t
--- response_body
type: worker
--- grep_error_log eval
qr/\[TRACE\s+\d+ init_worker_by_lua\(nginx.conf:\d+\):\d+ loop\]|\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):\d loop\]/
--- grep_error_log_out eval
[
qr/\[TRACE\s+\d+ init_worker_by_lua\(nginx.conf:\d+\):\d+ loop\]
\[TRACE\s+\d+ content_by_lua\(nginx.conf:\d+\):\d+ loop\]
/,
qr/\[TRACE\s+\d+ init_worker_by_lua\(nginx.conf:\d+\):\d+ loop\]
\[TRACE\s+\d+ content_by_lua\(nginx.conf:\d+\):\d+ loop\]
/
]
--- no_error_log
[error]
 -- NYI:
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2
