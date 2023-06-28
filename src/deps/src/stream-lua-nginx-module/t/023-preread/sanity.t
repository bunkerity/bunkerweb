# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#no_nginx_manager();
#log_level('warn');
#master_on();

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 3);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: basic print
--- stream_server_config
    preread_by_lua_block { ngx.print("Hello, Lua!\n") }

    content_by_lua return;
    #content_by_lua 'ngx.say("Hi")';
--- stream_response
Hello, Lua!



=== TEST 2: basic say
--- stream_server_config
    preread_by_lua_block {
        ngx.say("Hello, Lua!")
        ngx.say("Yay! ", 123);
    }

    content_by_lua_block { ngx.exit(ngx.OK) }
--- stream_response
Hello, Lua!
Yay! 123



=== TEST 3: no ngx.echo
--- stream_server_config
    preread_by_lua_block { ngx.echo("Hello, Lua!\\n") }
    content_by_lua_block { ngx.exit(ngx.OK) }
--- error_log
attempt to call field 'echo' (a nil value)



=== TEST 4: variable
--- stream_server_config
    # NOTE: the newline escape sequence must be double-escaped, as nginx config
    # parser will unescape first!
    preread_by_lua_block { v = ngx.var["remote_addr"] ngx.print("remote_addr: ", v, "\n") }
    content_by_lua_block { ngx.exit(ngx.OK) }
--- stream_response
remote_addr: 127.0.0.1



=== TEST 5: variable (file)
--- stream_server_config
    preread_by_lua_file html/test.lua;
    content_by_lua_block { ngx.exit(ngx.OK) }
--- user_files
>>> test.lua
v = ngx.var["remote_addr"]
ngx.print("remote_addr: ", v, "\n")
--- stream_response
remote_addr: 127.0.0.1



=== TEST 6: nil is "nil"
--- stream_server_config
    preread_by_lua_block { ngx.say(nil) }

    content_by_lua return;
--- stream_response
nil



=== TEST 7: write boolean
--- stream_server_config
    preread_by_lua_block { ngx.say(true, " ", false) }

    content_by_lua return;
--- stream_response
true false



=== TEST 8: nginx quote sql string 1
--- stream_server_config
    preread_by_lua_block { ngx.say(ngx.quote_sql_str('hello\n\r\'"\\')) }
    content_by_lua_block { ngx.exit(ngx.OK) }
--- stream_response
'hello\n\r\'\"\\'



=== TEST 9: nginx quote sql string 2
--- stream_server_config
    preread_by_lua_block { ngx.say(ngx.quote_sql_str("hello\n\r'\"\\")) }
    content_by_lua_block { ngx.exit(ngx.OK) }
--- stream_response
'hello\n\r\'\"\\'



=== TEST 10: use dollar
--- stream_server_config
    preread_by_lua_block {
        local s = "hello 112";
        ngx.say(string.find(s, "%d+$"));
    }

    content_by_lua_block { ngx.exit(ngx.OK) }
--- stream_response
79



=== TEST 11: short circuit
--- stream_server_config
    preread_by_lua_block {
        ngx.say("Hi")
        ngx.eof()
        ngx.exit(ngx.OK)
    }

    content_by_lua_block {
            print("HERE")
            ngx.print("BAD")
    }
--- stream_response
Hi



=== TEST 12: nginx vars in script path
--- stream_server_config
    preread_by_lua_file html/$remote_addr.lua;

    content_by_lua_block {
            print("HERE")
            ngx.print("BAD")
    }
--- user_files
>>> 127.0.0.1.lua
ngx.say("Hi")
ngx.eof()
ngx.exit(ngx.OK)
--- stream_response
Hi



=== TEST 13: phase postponing works
--- stream_server_config
    ssl_preread on;
    preread_by_lua_block {
        local n = ngx.var.ssl_preread_server_name

        if n then
            ngx.log(ngx.INFO, "$ssl_preread_server_name = " .. n)
        end

        if n == "my.sni.server.name" then
            ngx.exit(200)
        end

        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", tonumber(ngx.var.server_port))
        if not ok then
            ngx.say(err)
            return ngx.exit(500)
        end

        local _, err = sock:sslhandshake(nil, "my.sni.server.name")
        if not err then
            ngx.say("did not error as expected")
            return ngx.exit(500)
        end

        sock:close()
    }

    return done;
--- stream_request
hello
--- stream_response chop
done
--- error_log
$ssl_preread_server_name = my.sni.server.name while prereading client data
--- no_error_log
[crit]
[warn]



=== TEST 14: Lua file does not exist
--- stream_server_config
    preread_by_lua_file html/test2.lua;
    return here;
--- user_files
>>> test.lua
v = ngx.var["remote_addr"]
ngx.print("remote_addr: ", v, "\n")
--- error_log eval
qr/failed to load external Lua file ".*?\btest2\.lua": cannot open .*? No such file or directory/
