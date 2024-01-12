# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 5);

add_block_preprocessor(sub {
    my $block = shift;

    my $stream_config = $block->stream_config || '';

    $stream_config .= <<_EOC_;
    lua_package_path '$t::TestCore::Stream::lua_package_path';
    init_by_lua_block {
        $t::TestCore::Stream::init_by_lua_block
        $init_by_lua_block

        local v
        local typ = (require "ngx.process").type
        for i = 1, 400 do
            v = typ()
        end

        package.loaded.process_type = v
    }
_EOC_

    $block->set_value("stream_config", $stream_config);
});

master_on();
#no_diff();
# no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        ngx.say("process type: ", package.loaded.process_type)
    }
--- stream_response
process type: master
--- grep_error_log eval
qr/\[TRACE\s+\d+ init_by_lua:\d+ loop\]/
--- grep_error_log_out eval
[
qr/\A\[TRACE\s+\d+ init_by_lua:\d+ loop\]
\z/,
qr/\A\[TRACE\s+\d+ init_by_lua:\d+ loop\]
\z/
]
--- no_error_log
[error]
 -- NYI:
--- skip_nginx: 5: < 1.11.2
