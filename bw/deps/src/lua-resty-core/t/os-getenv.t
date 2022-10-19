# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

plan tests => repeat_each() * (blocks() * 3 + 1);

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }
});

$ENV{TEST_NGINX_BAR} = 'world';
$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::lua_package_path";

run_tests();

__DATA__

=== TEST 1: env directive explicit value is visible within init_by_lua*
--- main_config
env FOO=hello;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say(package.loaded.foo, "\n", os.getenv("FOO"))
    }
}
--- response_body
hello
hello



=== TEST 2: env directive explicit value is visible within init_by_lua* with lua_shared_dict
--- main_config
env FOO=hello;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    lua_shared_dict dogs 24k;

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say(package.loaded.foo, "\n", os.getenv("FOO"))
    }
}
--- response_body
hello
hello



=== TEST 3: env directive explicit value is case-sensitive within init_by_lua*
--- main_config
env FOO=hello;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("foo")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say(package.loaded.foo, "\n", os.getenv("foo"))
    }
}
--- response_body
nil
nil



=== TEST 4: env directives with no value are ignored
--- main_config
env FOO;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say(package.loaded.foo, "\n", os.getenv("FOO"))
    }
}
--- response_body
nil
nil



=== TEST 5: env is visible from environment
--- main_config
env TEST_NGINX_BAR;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("TEST_NGINX_BAR")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say(package.loaded.foo, "\n", os.getenv("TEST_NGINX_BAR"))
    }
}
--- response_body
world
world



=== TEST 6: env explicit set vs environment set
--- main_config
env TEST_NGINX_BAR=goodbye;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("TEST_NGINX_BAR")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say(package.loaded.foo, "\n", os.getenv("TEST_NGINX_BAR"))
    }
}
--- response_body
goodbye
goodbye



=== TEST 7: env directive with empty value
--- main_config
env FOO=;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        require "resty.core"
        package.loaded.foo = os.getenv("FOO")
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say("in init: ", package.loaded.foo, "\n",
                "in content: ", os.getenv("FOO"))
    }
}
--- response_body_like
in init:\s+
in content:\s+



=== TEST 8: os.getenv() overwrite is reverted in worker phases
--- main_config
env FOO=hello;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        package.loaded.init_os_getenv = os.getenv
    }
--- config
location /t {
    content_by_lua_block {
        ngx.say("FOO=", os.getenv("FOO"))

        if os.getenv ~= package.loaded.init_os_getenv then
            ngx.say("os.getenv() overwrite was reverted")

        else
            ngx.say("os.getenv() overwrite was not reverted")
        end
    }
}
--- response_body
FOO=hello
os.getenv() overwrite was reverted



=== TEST 9: os.getenv() can be localized after loading resty.core
--- main_config
env FOO=hello;
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        do
            local getenv = os.getenv

            package.loaded.f = function ()
                ngx.log(ngx.NOTICE, "FOO: ", getenv("FOO"))
            end
        end

        require "resty.core"

        package.loaded.f()

        package.loaded.is_os_getenv = os.getenv == package.loaded.os_getenv
    }
--- config
location /t {
    content_by_lua_block {
        package.loaded.f()
        package.loaded.f()

        if os.getenv ~= package.loaded.init_os_getenv then
            ngx.say("os.getenv() overwrite was reverted")

        else
            ngx.say("os.getenv() overwrite was not reverted")
        end
    }
}
--- response_body
os.getenv() overwrite was reverted
--- grep_error_log eval
qr/FOO: [a-z]+/
--- grep_error_log_out
FOO: hello
FOO: hello
FOO: hello
