package t::TestCore::Stream;

use Test::Nginx::Socket::Lua::Stream -Base;
use Cwd qw(cwd);

$ENV{TEST_NGINX_HOTLOOP} ||= 10;

our $pwd = cwd();

our $lua_package_path = './lib/?.lua;../lua-resty-lrucache/lib/?.lua;;';

our $init_by_lua_block = <<_EOC_;
    local verbose = false
    if verbose then
        local dump = require "jit.dump"
        dump.on("b", "$Test::Nginx::Util::ErrLogFile")
    else
        local v = require "jit.v"
        v.on("$Test::Nginx::Util::ErrLogFile")
    end

    require "resty.core"
    jit.opt.start("hotloop=$ENV{TEST_NGINX_HOTLOOP}")
    -- jit.off()
_EOC_

our $StreamConfig = <<_EOC_;
    lua_package_path '$lua_package_path';

    init_by_lua_block {
        $t::TestCore::Stream::init_by_lua_block
    }
_EOC_

our @EXPORT = qw(
    $pwd
    $lua_package_path
    $init_by_lua_block
    $StreamConfig
);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->stream_config) {
        $block->set_value("stream_config", $StreamConfig);
    }
});

1;
