package t::TestCore::Stream;

use Test::Nginx::Socket::Lua::Stream -Base;
use Cwd qw(cwd);
use Test::Nginx::Util 'is_tcp_port_used';

$ENV{TEST_NGINX_HOTLOOP} ||= 10;

sub get_unused_port ($);

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
    get_unused_port
);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->stream_config) {
        $block->set_value("stream_config", $StreamConfig);
    }
});

sub get_unused_port ($) {
    my $port = shift;

    my $i = 1000;
    srand($$); # reset the random seed
    while ($i-- > 0) {
        my $rand_port = $port + int(rand(65535 - $port));
        if (!is_tcp_port_used $rand_port) {
            #warn "found unused port $rand_port, pid $$\n";
            return $rand_port;
        }
    }

    die "no unused port available";
}

1;
