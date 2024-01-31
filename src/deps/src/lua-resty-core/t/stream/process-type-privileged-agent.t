# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4) - 2;

add_block_preprocessor(sub {
    my $block = shift;

    my $stream_config = $block->stream_config || '';

    $stream_config .= <<_EOC_;
    lua_package_path '$t::TestCore::Stream::lua_package_path';
    init_by_lua_block {
        $t::TestCore::Stream::init_by_lua_block
        $init_by_lua_block

        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent()
        if not ok then
            ngx.log(ngx.ERR, "enable_privileged_agent failed: ", err)
        end
    }

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local v
        local typ = (require "ngx.process").type
        for i = 1, 400 do
            v = typ()
        end

        if v == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", v)
        end
    }
_EOC_

    $block->set_value("stream_config", $stream_config);
});

#no_diff();
# no_long_string();
master_process_enabled(1);
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        ngx.sleep(0.1)
        local v
        local typ = require "ngx.process".type
        for i = 1, 200 do
            v = typ()
        end

        ngx.say("type: ", v)
    }
--- stream_response
type: worker
--- grep_error_log eval
qr/\[TRACE\s+\d+ init_worker_by_lua:\d+ loop\]|\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):\d+ loop\]|init_worker_by_lua:\d+: process type: \w+/
--- grep_error_log_out eval
[
qr/\[TRACE\s+\d+ init_worker_by_lua:\d+ loop\]
(?:\[TRACE\s+\d+ init_worker_by_lua:\d+ loop\]
)?\[TRACE\s+\d+ content_by_lua\(nginx.conf:\d+\):\d+ loop\]
init_worker_by_lua:10: process type: privileged
/,
qr/\[TRACE\s+\d+ init_worker_by_lua:\d+ loop\]
(?:\[TRACE\s+\d+ init_worker_by_lua:\d+ loop\]
)?\[TRACE\s+\d+ content_by_lua\(nginx.conf:\d+\):\d+ loop\]
init_worker_by_lua:10: process type: privileged
/
]
--- no_error_log
[error]
 -- NYI:
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2



=== TEST 2: `enable_privileged_agent` disabled
--- stream_server_config
    content_by_lua_block {
        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent()
        if not ok then
            error(err)
        end
    }
--- error_log eval
qr/\[error\] .*? API disabled in the current context/
--- skip_nginx: 3: < 1.11.2
