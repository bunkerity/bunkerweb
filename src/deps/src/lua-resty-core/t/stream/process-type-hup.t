# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4);

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
        local typ = require "ngx.process".type

        if typ() == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", typ())
        end
    }
_EOC_

    $block->set_value("stream_config", $stream_config);
});

master_on();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        local typ = require "ngx.process".type

        local f, err = io.open(ngx.config.prefix() .. "/logs/nginx.pid", "r")
        if not f then
            ngx.say("failed to open nginx.pid: ", err)
            return
        end

        local pid = f:read()
        -- ngx.say("master pid: [", pid, "]")

        f:close()

        ngx.say("type: ", typ())
        os.execute("kill -HUP " .. pid)
    }
--- stream_response
type: worker
--- error_log
init_worker_by_lua:6: process type: privileged
--- no_error_log
[error]
--- skip_nginx: 4: < 1.11.2
--- wait: 0.1
