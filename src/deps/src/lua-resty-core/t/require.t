# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

plan tests => repeat_each() * blocks() * 3;

add_block_preprocessor(sub {
    my $block = shift;

    my $http_config = $block->http_config || '';
    my $init_by_lua_block = $block->init_by_lua_block || '';

    $http_config .= <<_EOC_;
    lua_package_path '\$prefix/html/?.lua;$t::TestCore::lua_package_path';
    init_by_lua_block {
        $t::TestCore::init_by_lua_block
        $init_by_lua_block
    }
_EOC_

    $block->set_value("http_config", $http_config);
});

no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: utils.str_replace_char() sanity (replaces a single character)
--- config
    location /t {
        content_by_lua_block {
            local has_foo, foo
            has_foo, foo= pcall(require, "foo")
            if not has_foo then
                ngx.say("failed to load foo: ", foo)
            end

            has_foo, foo = pcall(require, "foo")
            if not has_foo then
                ngx.say("failed to load foo again: ", foo)
            else
                ngx.say("type(a)=", type(a), " foo=", foo)
            end
        }
    }
--- user_files
>>> foo.lua
local ffi = require("ffi")

local _M = {}

ffi.cdef[[
int xxxx();
]]

local function get_caches_array()
    return tonumber(ffi.C.xxxx())
end

local a = get_caches_array()

_M.a = a
_M.get_caches_array = get_caches_array

return _M
--- request
GET /t
--- response_body eval
qr|failed to load foo: .*/html/foo.lua:10: .*/lib/libluajit-5.1.so.2: undefined symbol: xxxx
failed to load foo again: ./lib/resty/core/base.lua:\d+: loop or previous error loading module 'foo'|ms
--- no_error_log
[error]
