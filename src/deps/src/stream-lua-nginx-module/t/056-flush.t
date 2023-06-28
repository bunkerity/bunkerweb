# vim:set ft= ts=4 sw=4 et fdm=marker:

BEGIN {
    $ENV{TEST_NGINX_POSTPONE_OUTPUT} = 1;
}

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * 12;

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: flush wait - content
--- stream_server_config
    content_by_lua_block {
        ngx.say("hello, world")
        local ok, err = ngx.flush(true)
        if not ok then
            ngx.log(ngx.ERR, "flush failed: ", err)
            return
        end
        ngx.say("hiya")
    }
--- stream_response
hello, world
hiya
--- no_error_log
[error]
--- error_log
lua reuse free buf memory 13 >= 5



=== TEST 2: flush no wait - content
--- stream_server_config
    lua_socket_send_timeout 500ms;
    content_by_lua_block {
        ngx.say("hello, world")
        local ok, err = ngx.flush(false)
        if not ok then
            ngx.log(ngx.ERR, "flush failed: ", err)
            return
        end
        ngx.say("hiya")
    }
--- stream_response
hello, world
hiya



=== TEST 3: flush wait - big data
--- stream_server_config
    content_by_lua_block {
        ngx.say(string.rep("a", 1024 * 64))
        ngx.flush(true)
        ngx.say("hiya")
    }
--- stream_response
hello, world
hiya
--- SKIP



=== TEST 4: flush wait in a user coroutine
--- stream_server_config
    content_by_lua_block {
        function f()
            ngx.say("hello, world")
            ngx.flush(true)
            coroutine.yield()
            ngx.say("hiya")
        end
        local c = coroutine.create(f)
        ngx.say(coroutine.resume(c))
        ngx.say(coroutine.resume(c))
    }
--- stap2
F(ngx_http_lua_wev_handler) {
    printf("wev handler: wev:%d\n", $r->connection->write->ready)
}

global ids, cur

function gen_id(k) {
    if (ids[k]) return ids[k]
    ids[k] = ++cur
    return cur
}

F(ngx_http_handler) {
    delete ids
    cur = 0
}

/*
F(ngx_http_lua_run_thread) {
    id = gen_id($ctx->cur_co)
    printf("run thread %d\n", id)
}

probe process("/usr/local/openresty-debug/luajit/lib/libluajit-5.1.so.2").function("lua_resume") {
    id = gen_id($L)
    printf("lua resume %d\n", id)
}
*/

M(http-lua-user-coroutine-resume) {
    p = gen_id($arg2)
    c = gen_id($arg3)
    printf("resume %x in %x\n", c, p)
}

M(http-lua-entry-coroutine-yield) {
    println("entry coroutine yield")
}

/*
F(ngx_http_lua_coroutine_yield) {
    printf("yield %x\n", gen_id($L))
}
*/

M(http-lua-user-coroutine-yield) {
    p = gen_id($arg2)
    c = gen_id($arg3)
    printf("yield %x in %x\n", c, p)
}

F(ngx_http_lua_atpanic) {
    printf("lua atpanic(%d):", gen_id($L))
    print_ubacktrace();
}

M(http-lua-user-coroutine-create) {
    p = gen_id($arg2)
    c = gen_id($arg3)
    printf("create %x in %x\n", c, p)
}

F(ngx_http_lua_ngx_exec) { println("exec") }

F(ngx_http_lua_ngx_exit) { println("exit") }

F(ngx_http_writer) { println("http writer") }

--- stream_response
hello, world
true
hiya
true
--- error_log
lua reuse free buf memory 13 >= 5



=== TEST 5: flush before sending out the header
--- stream_server_config
    content_by_lua_block {
        ngx.flush()
        ngx.status = 404
        ngx.say("not found")
    }
--- stream_response
not found
--- no_error_log
[error]



=== TEST 6: limit_rate
TODO
--- SKIP
--- stream_server_config
        limit_rate 150;
    content_by_lua_block {
        local begin = ngx.now()
        for i = 1, 2 do
            ngx.print(string.rep("a", 100))
            local ok, err = ngx.flush(true)
            if not ok then
                ngx.log(ngx.ERR, "failed to flush: ", err)
            end
        end
        local elapsed = ngx.now() - begin
        ngx.log(ngx.WARN, "lua writes elapsed ", elapsed, " sec")
    }
--- stream_response eval
"a" x 200
--- error_log eval
[
qr/lua writes elapsed [12](?:\.\d+)? sec/,
qr/lua flush requires waiting: buffered 0x[0-9a-f]+, delayed:1/,
]

--- no_error_log
[error]
--- timeout: 4
