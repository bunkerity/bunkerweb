# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
log_level('debug');

repeat_each(2);

plan tests => repeat_each() * 21;

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: sleep 0.5
--- stream_server_config
    preread_by_lua_block {
            ngx.update_time()
            local before = ngx.now()
            ngx.sleep(0.5)
            local now = ngx.now()
            ngx.say(now - before)
            ngx.exit(200)
    }

    return here;
--- stream_response_like chop
^0\.(?:4[5-9]\d*|5[0-9]\d*|5)$
--- error_log
lua ready to sleep for
stream lua sleep timer expired



=== TEST 2: sleep ag
--- stream_server_config
    preread_by_lua_block {
            ngx.update_time()
            local before = ngx.now()
            ngx.sleep("a")
            local now = ngx.now()
            ngx.say(now - before)
            ngx.exit(200)
    }

    return here;
--- error_log
bad argument #1 to 'sleep'



=== TEST 3: sleep 0.5 - multi-times
--- stream_server_config
    preread_by_lua_block {
        ngx.update_time()
        local start = ngx.now()
        ngx.sleep(0.3)
        ngx.sleep(0.3)
        ngx.sleep(0.3)
        ngx.say(ngx.now() - start)
        ngx.exit(200)
    }

    return here;
--- stream_response_like chop
^0\.(?:8[5-9]\d*|9[0-9]\d*|9)$
--- error_log
lua ready to sleep for
stream lua sleep timer expired
--- no_error_log
[error]



=== TEST 4: sleep 0.5 - interleaved by ngx.say() - ended by ngx.sleep
--- stream_server_config
    preread_by_lua_block {
        ngx.sleep(1)
        ngx.say("blah")
        ngx.sleep(1)
        ngx.exit(200)
    }

    return here;
--- stream_response
blah
--- error_log
lua ready to sleep
stream lua sleep timer expired
--- no_error_log
[error]



=== TEST 5: sleep 0.5 - interleaved by ngx.say() - not ended by ngx.sleep
--- stream_server_config
    preread_by_lua_block {
        ngx.sleep(0.3)
        ngx.say("blah")
        ngx.sleep(0.5)
        ngx.say("hiya")
        ngx.exit(200)
    }

    return here;
--- stream_response
blah
hiya
--- error_log
lua ready to sleep for
stream lua sleep timer expired
--- no_error_log
[error]
