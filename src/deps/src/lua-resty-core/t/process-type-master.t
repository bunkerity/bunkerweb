# vim:set ft= ts=4 sw=4 et fdm=marker:

BEGIN {
    undef $ENV{TEST_NGINX_USE_STAP};
}

use lib '.';
use t::TestCore;
use Cwd qw(cwd);

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5);

my $pwd = cwd();

our $HttpConfig = <<_EOC_;
    lua_package_path "$t::TestCore::lua_package_path";
    init_by_lua_block {
        $t::TestCore::init_by_lua_block

        local v
        local typ = (require "ngx.process").type
        for i = 1, 400 do
            v = typ()
        end

        package.loaded.process_type = v
    }
_EOC_

#worker_connections(1014);
master_on();
#log_level('error');

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
            ngx.say("process type: ", package.loaded.process_type)
        }
    }
--- request
GET /t
--- response_body
process type: master
--- grep_error_log eval
qr/\[TRACE\s+\d+ init_by_lua\(nginx.conf:\d+\):\d+ loop\]/
--- grep_error_log_out eval
[
qr/\A\[TRACE\s+\d+ init_by_lua\(nginx.conf:\d+\):\d+ loop\]
\z/,
qr/\A\[TRACE\s+\d+ init_by_lua\(nginx.conf:\d+\):\d+ loop\]
\z/
]
--- no_error_log
[error]
 -- NYI:
--- skip_nginx: 5: < 1.11.2
