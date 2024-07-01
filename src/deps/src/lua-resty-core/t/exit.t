# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

repeat_each(120);
#repeat_each(2);

plan tests => repeat_each() * (blocks() * 5);

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

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- config
    location = /t {
        content_by_lua_block {
            ngx.exit(403)
        }
    }
--- request
GET /t
--- response_body_like: 403 Forbidden
--- error_code: 403
--- no_error_log eval
["[error]",
qr/ -- NYI: (?!FastFunc coroutine.yield)/,
" bad argument"]



=== TEST 2: call ngx.exit() from a custom lua module
--- config
    location = /t {
        content_by_lua_block {
            local foo = require "foo"
            foo.go()
        }
    }
--- user_files
>>> foo.lua
local exit = ngx.exit

local function go()
    exit(403)
    return
end

return { go = go }
--- request
GET /t
--- response_body_like: 403 Forbidden
--- error_code: 403
--- no_error_log eval
["[error]",
qr/ -- NYI: (?!FastFunc coroutine.yield)/,
" bad argument"]



=== TEST 3: accepts NGX_OK
--- config
    location = /t {
        content_by_lua_block {
            ngx.exit(ngx.OK)
        }
    }
--- request
GET /t
--- response_body
--- no_error_log eval
["[error]",
qr/ -- NYI: (?!FastFunc coroutine.yield)/,
" bad argument"]



=== TEST 4: accepts NGX_ERROR
--- config
    location = /t {
        content_by_lua_block {
            ngx.exit(ngx.ERROR)
        }
    }
--- request
GET /t
--- error_code:
--- response_body
--- no_error_log eval
["[error]",
qr/ -- NYI: (?!FastFunc coroutine.yield)/,
" bad argument"]



=== TEST 5: accepts NGX_DECLINED
--- config
    location = /t {
        content_by_lua_block {
            ngx.exit(ngx.DECLINED)
        }
    }
--- request
GET /t
--- error_code:
--- response_body
--- no_error_log eval
["[error]",
qr/ -- NYI: (?!FastFunc coroutine.yield)/,
" bad argument"]



=== TEST 6: refuses NGX_AGAIN
--- config
    location = /t {
        content_by_lua_block {
            ngx.exit(ngx.AGAIN)
        }
    }
--- request
GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? bad argument to 'ngx.exit': does not accept NGX_AGAIN or NGX_DONE/
--- no_error_log eval
qr/ -- NYI: (?!FastFunc coroutine.yield)/
[crit]



=== TEST 7: refuses NGX_DONE
--- config
    location = /t {
        content_by_lua_block {
            ngx.exit(ngx.DONE)
        }
    }
--- request
GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? bad argument to 'ngx.exit': does not accept NGX_AGAIN or NGX_DONE/
--- no_error_log eval
qr/ -- NYI: (?!FastFunc coroutine.yield)/
[crit]
