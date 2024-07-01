# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

add_block_preprocessor(sub {
    my $block = shift;

    my $stream_config = $block->stream_config || '';

    $stream_config .= <<_EOC_;
    init_by_lua_block {
        function test_sa_restart()
            local signals = {
                --"HUP",
                --"INFO",
                --"XCPU",
                --"USR1",
                --"USR2",
                "ALRM",
                --"INT",
                "IO",
                "CHLD",
                --"WINCH",
            }

            for _, signame in ipairs(signals) do
                local cmd = string.format("kill -s %s %d && sleep 0.01",
                                          signame, ngx.worker.pid())
                local err = select(2, io.popen(cmd):read("*a"))
                if err then
                    error("SIG" .. signame .. " caused: " .. err)
                end
            end
        end
    }
_EOC_

    $block->set_value("stream_config", $stream_config);

    if (!defined $block->stream_server_config) {
        my $stream_config = <<_EOC_;
            content_by_lua_block {
                ngx.say("ok")
            }
_EOC_

        $block->set_value("stream_server_config", $stream_config);
    }

    if (!defined $block->no_error_log) {
        $block->set_value("no_error_log", "[error]");
    }
});

plan tests => repeat_each() * (blocks() * 2 + 1);

no_long_string();
run_tests();

__DATA__

=== TEST 1: lua_sa_restart default - sets SA_RESTART in init_worker_by_lua*
--- stream_config
    init_worker_by_lua_block {
        test_sa_restart()
    }



=== TEST 2: lua_sa_restart off - does not set SA_RESTART
We must specify the lua_sa_restart directive in the http block as well, since
otherwise, ngx_lua's own default of lua_sa_restart is 'on', and ngx_lua
re-enables the SA_RESTART flag.
--- http_config
    lua_sa_restart off;
--- stream_config
    lua_sa_restart off;

    init_worker_by_lua_block {
        test_sa_restart()
    }
--- no_error_log
[crit]
--- error_log
Interrupted system call



=== TEST 3: lua_sa_restart on (default) - sets SA_RESTART if no init_worker_by_lua* phase is defined
--- stream_server_config
    content_by_lua_block {
        test_sa_restart()
    }



=== TEST 4: lua_sa_restart on (default) - SA_RESTART is effective in content_by_lua*
--- stream_server_config
    content_by_lua_block {
        test_sa_restart()
    }



=== TEST 5: lua_sa_restart on (default) - SA_RESTART is effective in log_by_lua*
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }

    log_by_lua_block {
        test_sa_restart()
    }



=== TEST 6: lua_sa_restart on (default) - SA_RESTART is effective in timer phase
--- stream_server_config
    content_by_lua_block {
        ngx.say("ok")
    }

    log_by_lua_block {
        ngx.timer.at(0, test_sa_restart)
    }
