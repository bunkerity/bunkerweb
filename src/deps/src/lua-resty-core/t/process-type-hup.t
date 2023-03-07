# vim:set ft= ts=4 sw=4 et fdm=marker:

our $SkipReason;

BEGIN {
    if ($ENV{TEST_NGINX_CHECK_LEAK}) {
        $SkipReason = "unavailable for the hup tests";

    } else {
        $ENV{TEST_NGINX_USE_HUP} = 1;
        undef $ENV{TEST_NGINX_USE_STAP};
    }
}

use lib '.';
use t::TestCore $SkipReason ? (skip_all => $SkipReason) : ();
use Cwd qw(cwd);

#worker_connections(1014);
master_process_enabled(1);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4);

my $pwd = cwd();

our $HttpConfig = <<_EOC_;
    lua_package_path '$t::TestCore::lua_package_path';
    init_by_lua_block {
        $t::TestCore::init_by_lua_block

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

#no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- http_config eval: $::HttpConfig
--- config
    location = /t {
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
    }
--- request
GET /t
--- response_body
type: worker
--- error_log
init_worker_by_lua(nginx.conf:48):6: process type: privileged
--- no_error_log
[error]
--- skip_nginx: 4: < 1.11.2
