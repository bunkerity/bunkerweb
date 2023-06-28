# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        ngx.ctx.foo = 32;
        ngx.say(ngx.ctx.foo)
    }
--- stream_response
32
--- no_error_log
[error]



=== TEST 2: rewrite, access, and content
TODO
--- stream_server_config
    rewrite_by_lua_block {
        print("foo = ", ngx.ctx.foo)
        ngx.ctx.foo = 76
    }
    access_by_lua_block {
        ngx.ctx.foo = ngx.ctx.foo + 3
    }
    content_by_lua_block {
        ngx.say(ngx.ctx.foo)
    }
--- stream_response
79
--- no_error_log
[error]
--- grep_error_log eval: qr/foo = [^,]+/
--- log_level: info
--- grep_error_log_out
foo = nil
--- SKIP



=== TEST 3: different requests have different ngx.ctx
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.ctx.foo)
        ngx.ctx.foo = 32
        ngx.say(ngx.ctx.foo)
    }
--- stream_server_config2
    content_by_lua_block {
        ngx.say(ngx.ctx.foo)
    }
--- stream_response
nil
32
nil
--- no_error_log
[error]



=== TEST 4: overriding ctx
--- stream_server_config
    content_by_lua_block {
        ngx.ctx = { foo = 32, bar = 54 };
        ngx.say(ngx.ctx.foo)
        ngx.say(ngx.ctx.bar)

        ngx.ctx = { baz = 56  };
        ngx.say(ngx.ctx.foo)
        ngx.say(ngx.ctx.baz)
    }
--- stream_response
32
54
nil
56
--- no_error_log
[error]



=== TEST 5: ngx.ctx + ngx.exit(ngx.ERROR) + log_by_lua
TODO
--- stream_server_config
    rewrite_by_lua_block {
        ngx.ctx.foo = 32;
        ngx.exit(ngx.ERROR)
    }
    log_by_lua_block { ngx.log(ngx.WARN, "ngx.ctx = ", ngx.ctx.foo) }
--- stream_response
--- no_error_log
[error]
--- error_log
ngx.ctx = 32
--- SKIP



=== TEST 6: ngx.ctx + ngx.exit(200) + log_by_lua
TODO
--- stream_server_config
    rewrite_by_lua_block {
        ngx.ctx.foo = 32;
        ngx.say(ngx.ctx.foo)
        ngx.exit(200)
    }
    log_by_lua 'ngx.log(ngx.WARN, "ctx.foo = ", ngx.ctx.foo)';
--- stream_response
32
--- no_error_log
[error]
--- error_log
ctx.foo = 32
--- SKIP
