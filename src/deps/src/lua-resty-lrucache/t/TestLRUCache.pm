package t::TestLRUCache;

use Test::Nginx::Socket::Lua -Base;
use Cwd qw(cwd);

$ENV{TEST_NGINX_HOTLOOP} ||= 10;

our $pwd = cwd();

our $lua_package_path = './lib/?.lua;;';

our $HttpConfig = <<_EOC_;
    lua_package_path '$lua_package_path';
_EOC_

our @EXPORT = qw(
    $pwd
    $lua_package_path
    $HttpConfig
);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->http_config) {
        $block->set_value("http_config", $HttpConfig);
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }

    if (!defined $block->no_error_log) {
        $block->set_value("no_error_log", "[error]");
    }
});

1;
