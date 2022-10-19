# vim:set ft= ts=4 sw=4 et fdm=marker:

our $SkipReason;

BEGIN {
    if ($ENV{TEST_NGINX_CHECK_LEAK}) {
        $SkipReason = "unavailable for the hup tests";

    } else {
        undef $ENV{TEST_NGINX_USE_STAP};
    }
}

use lib '.';
use t::TestCore::Stream $SkipReason ? (skip_all => $SkipReason) : ();

plan tests => repeat_each() * (blocks() * 2 + 1);

no_shuffle();
use_hup();

$ENV{TEST_NGINX_BAR} = 'old';
$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::Stream::lua_package_path";

run_tests();

__DATA__

=== TEST 1: env directive explicit value is visible within init_by_lua*
--- main_config
env FOO=old;
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(package.loaded.foo)
    }
--- stream_response
old
--- error_log
[notice]



=== TEST 2: HUP reload changes env value (1/3)
--- main_config
env FOO=new;
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(package.loaded.foo)
    }
--- stream_response
new



=== TEST 3: HUP reload changes env value (2/3)
--- main_config
env FOO=;
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(package.loaded.foo)
    }
--- stream_response_like chomp
\s



=== TEST 4: HUP reload changes env value (3/3)
--- main_config
env FOO;
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(package.loaded.foo)
    }
--- stream_response
nil



=== TEST 5: HUP reload changes visible environment variable (1/2)
--- main_config
env TEST_NGINX_BAR;
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.test_nginx_bar = os.getenv("TEST_NGINX_BAR")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(package.loaded.test_nginx_bar)
    }
--- stream_response
old



=== TEST 6: HUP reload changes visible environment variable (2/2)
--- main_config
env TEST_NGINX_BAR=new;
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.test_nginx_bar = os.getenv("TEST_NGINX_BAR")
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(package.loaded.test_nginx_bar)
    }
--- stream_response
new
