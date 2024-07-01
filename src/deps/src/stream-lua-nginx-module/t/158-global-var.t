# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

log_level('debug');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 8);

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_HTML_DIR} ||= html_dir();

no_long_string();

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

});

run_tests();

__DATA__

=== TEST 1: init_by_lua
--- stream_config
    init_by_lua_block {
        foo = 1
    }
--- stream_server_config
    content_by_lua_block {
        if not foo then
            foo = 1
        else
            ngx.log(ngx.WARN, "old foo: ", foo)
            foo = foo + 1
        end
        ngx.say(foo)
    }
--- stream_response_like eval
qr/^(2|3)$/
--- grep_error_log eval: qr/old foo: \d+/
--- grep_error_log_out eval
["old foo: 1\n", "old foo: 2\n"]



=== TEST 2: init_worker_by_lua
--- stream_config
    init_worker_by_lua_block {
        if not foo then
            foo = 1
        else
            ngx.log(ngx.WARN, "old foo: ", foo)
            foo = foo + 1
        end
    }
--- stream_server_config
    content_by_lua_block {
        if not foo then
            foo = 1
        else
            ngx.log(ngx.WARN, "old foo: ", foo)
            foo = foo + 1
        end
        ngx.say(foo)
    }
--- stream_response_like eval
qr/^(2|3)$/
--- grep_error_log eval: qr/old foo: \d+/
--- grep_error_log_out eval
["old foo: 1\n", "old foo: 2\n"]



=== TEST 3: preread_by_lua
--- stream_server_config
    preread_by_lua_block {
        if not foo then
            foo = 1
        else
            ngx.log(ngx.WARN, "old foo: ", foo)
            foo = foo + 1
        end
        ngx.say(foo)
    }
    content_by_lua_block {
    }
--- stream_response_like chomp
\A[12]\n\z
--- grep_error_log eval
qr/(old foo: \d+|\[\w+\].*?writing a global Lua variable \('[^'\s]+'\)|\w+_by_lua\(.*?\):\d+: in main chunk)/
--- grep_error_log_out eval
[qr/\A\[warn\] .*?writing a global Lua variable \('foo'\)
preread_by_lua\(nginx\.conf:\d+\):3: in main chunk/, "old foo: 1\n"]



=== TEST 4: content_by_lua
--- stream_server_config
    content_by_lua_block {
        if not foo then
            foo = 1
        else
            ngx.log(ngx.WARN, "old foo: ", foo)
            foo = foo + 1
        end
        ngx.say(foo)
    }
--- stream_response_like chomp
\A[12]\n\z
--- grep_error_log eval
qr/(old foo: \d+|\[\w+\].*?writing a global Lua variable \('[^'\s]+'\)|\w+_by_lua\(.*?\):\d+: in main chunk, )/
--- grep_error_log_out eval
[qr/\A\[warn\] .*?writing a global Lua variable \('foo'\)
content_by_lua\(nginx\.conf:\d+\):3: in main chunk, \n\z/, "old foo: 1\n"]



=== TEST 5: log_by_lua
--- stream_server_config
    content_by_lua_block {
        ngx.say(foo)
    }
    log_by_lua_block {
        if not foo then
            foo = 1
        else
            ngx.log(ngx.WARN, "old foo: ", foo)
            foo = foo + 1
        end
    }
--- stream_response_like chomp
\A(?:nil|1)\n\z
--- grep_error_log eval
qr/(old foo: \d+|\[\w+\].*?writing a global Lua variable \('[^'\s]+'\)|\w+_by_lua\(.*?\):\d+: in main chunk)/
--- grep_error_log_out eval
[qr/\A\[warn\] .*?writing a global Lua variable \('foo'\)
log_by_lua\(nginx\.conf:\d+\):3: in main chunk/, "old foo: 1\n"]



=== TEST 6: timer
--- stream_server_config
    content_by_lua_block {
        local function f()
            if not foo then
                foo = 1
            else
                ngx.log(ngx.WARN, "old foo: ", foo)
                foo = foo + 1
            end
        end
        local ok, err = ngx.timer.at(0, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.sleep(0.01)
        ngx.say(foo)
    }
--- stream_response_like chomp
\A[12]\n\z
--- grep_error_log eval
qr/(old foo: \d+|\[\w+\].*?writing a global Lua variable \('[^'\s]+'\)|\w+_by_lua\(.*?\):\d+: in\b)/
--- grep_error_log_out eval
[qr/\A\[warn\] .*?writing a global Lua variable \('foo'\)
content_by_lua\(nginx\.conf:\d+\):4: in\n\z/, "old foo: 1\n"]



=== TEST 7: uthread
--- stream_server_config
    content_by_lua_block {
        local function f()
            if not foo then
                foo = 1
            else
                ngx.log(ngx.WARN, "old foo: ", foo)
                foo = foo + 1
            end
        end
        local ok, err = ngx.thread.spawn(f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.sleep(0.01)
        ngx.say(foo)
    }
--- stream_response_like chomp
\A[12]\n\z
--- grep_error_log eval
qr/(old foo: \d+|writing a global Lua variable \('\w+'\))/
--- grep_error_log_out eval
["writing a global Lua variable \('foo'\)\n", "old foo: 1\n"]



=== TEST 8: balancer_by_lua
--- stream_config
    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            if not foo then
                foo = 1
            else
                ngx.log(ngx.WARN, "old foo: ", foo)
                foo = foo + 1
            end
        }
    }
--- stream_server_config
        proxy_pass backend;
--- grep_error_log eval: qr/(old foo: \d+|writing a global Lua variable \('\w+'\))/
--- grep_error_log_out eval
["writing a global Lua variable \('foo'\)\n", "old foo: 1\n"]
--- error_log
connect() to 0.0.0.1:1234 failed



=== TEST 9: warn messages for polluting _G table when handling request
--- stream_server_config
        content_by_lua_block {
            if not foo then
                foo = 0

            elseif not foo1 then
                _G[1] = 2
            end

            ngx.say(foo)
        }
--- stream_response
0
--- grep_error_log eval: qr/writing a global Lua variable \('\w+'\)/
--- grep_error_log_out eval
["writing a global Lua variable \('foo'\)\n", "writing a global Lua variable \('1'\)\n"]



=== TEST 10: don't show warn messages in init/init_worker
--- stream_config
    init_by_lua_block {
        foo = 1
    }

    init_worker_by_lua_block {
        bar = 2
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say(foo)
        ngx.say(bar)
    }
--- stream_response
1
2
--- no_error_log
setting global variable
