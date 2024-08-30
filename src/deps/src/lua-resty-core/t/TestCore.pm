package t::TestCore;

use Test::Nginx::Socket::Lua -Base;
use Cwd qw(cwd realpath abs_path);
use File::Basename;
use Test::Nginx::Util 'is_tcp_port_used';

$ENV{TEST_NGINX_HOTLOOP} ||= 10;
$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_CERT_DIR} ||= dirname(realpath(abs_path(__FILE__)));

sub get_unused_port ($);

$ENV{TEST_NGINX_SERVER_SSL_PORT} ||= get_unused_port 23456;

our $pwd = cwd();

our $lua_package_path = './lib/?.lua;./t/lib/?.lua;../lua-resty-lrucache/lib/?.lua;;';

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

our $HttpConfig = <<_EOC_;
    lua_package_path '$lua_package_path';

    init_by_lua_block {
        $t::TestCore::init_by_lua_block
    }
_EOC_

our @EXPORT = qw(
    $pwd
    $lua_package_path
    $init_by_lua_block
    $HttpConfig
    get_unused_port
);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->http_config) {
        $block->set_value("http_config", $HttpConfig);
    }

    if ($Test::Nginx::Util::UseValgrind) {
        my $timeout = $block->timeout || 3;
        $timeout *= 5;
        $block->set_value("timeout", $timeout);
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
