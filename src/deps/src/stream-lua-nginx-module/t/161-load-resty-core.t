use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

our $HtmlDir = html_dir;

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->no_error_log) {
        $block->set_value("no_error_log", "[error]");
    }
});

no_long_string();
run_tests();

__DATA__

=== TEST 1: lua_load_resty_core is automatically loaded in the Lua VM
--- stream_server_config
    content_by_lua_block {
        local loaded_resty_core = package.loaded["resty.core"]
        local resty_core = require "resty.core"

        ngx.say("resty.core loaded: ", loaded_resty_core == resty_core)
    }
--- stream_response
resty.core loaded: true



=== TEST 2: resty.core is automatically loaded in the Lua VM when 'lua_shared_dict' is used
--- stream_config
    lua_shared_dict dogs 128k;
--- stream_server_config
    content_by_lua_block {
        local loaded_resty_core = package.loaded["resty.core"]
        local resty_core = require "resty.core"

        ngx.say("resty.core loaded: ", loaded_resty_core == resty_core)
    }
--- stream_response
resty.core loaded: true



=== TEST 3: resty.core is automatically loaded in the Lua VM with 'lua_code_cache off'
--- stream_config
    lua_code_cache off;
--- stream_server_config
    content_by_lua_block {
        local loaded_resty_core = package.loaded["resty.core"]
        local resty_core = require "resty.core"

        ngx.say("resty.core loaded: ", loaded_resty_core ~= nil)
    }
--- stream_response
resty.core loaded: true



=== TEST 4: resty.core loading honors the lua_package_path directive
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local loaded_resty_core = package.loaded["resty.core"]
        local resty_core = require "resty.core"

        ngx.say("resty.core loaded: ", loaded_resty_core == resty_core)

        resty_core.go()
    }
--- stream_response
resty.core loaded: true
loaded from html dir
--- user_files
>>> resty/core.lua
return {
    go = function ()
        ngx.say("loaded from html dir")
    end
}



=== TEST 5: resty.core not loading aborts the initialization
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;';"
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }
--- must_die
--- error_log eval
qr/\[alert\] .*? failed to load the 'resty\.core' module .*? \(reason: module 'resty\.core' not found:/



=== TEST 6: resty.core not loading produces an error with 'lua_code_cache off'
--- stream_config
    lua_code_cache off;

    init_by_lua_block {
        package.path = ""
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }
--- error_log eval
qr/\[error\] .*? failed to load the 'resty\.core' module .*? \(reason: module 'resty\.core' not found:/
--- no_error_log eval
qr/\[alert\] .*? failed to load the 'resty\.core' module/



=== TEST 7: lua_load_resty_core logs a deprecation warning when specified (on)
--- stream_config
    lua_load_resty_core on;
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }
--- grep_error_log eval: qr/\[warn\] .*? lua_load_resty_core is deprecated.*/
--- grep_error_log_out eval
[
qr/\[warn\] .*? lua_load_resty_core is deprecated \(the lua-resty-core library is required since ngx_stream_lua v0\.0\.8\) in .*?nginx\.conf:\d+/,
""
]



=== TEST 8: lua_load_resty_core logs a deprecation warning when specified (off)
--- stream_config
    lua_load_resty_core off;
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }
--- grep_error_log eval: qr/\[warn\] .*? lua_load_resty_core is deprecated.*/
--- grep_error_log_out eval
[
qr/\[warn\] .*? lua_load_resty_core is deprecated \(the lua-resty-core library is required since ngx_stream_lua v0\.0\.8\) in .*?nginx\.conf:\d+/,
""
]
