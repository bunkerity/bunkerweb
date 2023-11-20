package t::TestKiller;

use v5.10.1;
use Test::Nginx::Socket::Lua -Base;

add_block_preprocessor(sub {
    my $block = shift;

    my $http_config = $block->http_config // '';
    my $init_by_lua_block = $block->init_by_lua_block // 'require "resty.core"';

    $http_config .= <<_EOC_;

    lua_package_path "./lib/?.lua;../lua-resty-core/lib/?.lua;../lua-resty-lrucache/lib/?.lua;;";
    lua_package_cpath "./?.so;;";
    init_by_lua_block {
        $init_by_lua_block
    }
_EOC_

    $block->set_value("http_config", $http_config);

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }
});

1;
