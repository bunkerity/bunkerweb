# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 1);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_config
    lua_add_variable $foo;
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.var.foo)
        ngx.var.foo = "bar"
        ngx.say(ngx.var.foo)
    }
--- stream_response
nil
bar
--- no_error_log
[warn]
[error]



=== TEST 2: works with C code
--- stream_config
    lua_add_variable $foo;
--- stream_server_config
    preread_by_lua_block {
        ngx.var.foo = "bar"
    }

    return $foo\n;
--- stream_response
bar
--- no_error_log
[warn]
[error]



=== TEST 3: multiple add with same name works
--- stream_config
    lua_add_variable $foo;
    lua_add_variable $foo;
--- stream_server_config
    preread_by_lua_block {
        ngx.var.foo = "bar"
    }

    return $foo\n;
--- stream_response
bar
--- no_error_log
[warn]
[error]



=== TEST 4: accessible in log phase
--- stream_config
    lua_add_variable $foo;

    log_format test "access log: $foo";
    access_log logs/error.log test;
--- stream_server_config
    preread_by_lua_block {
        ngx.var.foo = "bar"
    }

    return $foo\n;
--- stream_response
bar
--- no_error_log
[warn]
[error]
--- error_log
access log: bar
