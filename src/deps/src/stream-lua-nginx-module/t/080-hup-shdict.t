# vim:set ft= ts=4 sw=4 et fdm=marker:

our $SkipReason;

BEGIN {
    if ($ENV{TEST_NGINX_CHECK_LEAK}) {
        $SkipReason = "unavailable for the hup tests";

    } else {
        $ENV{TEST_NGINX_USE_HUP} = 1;
        undef $ENV{TEST_NGINX_USE_STAP};
    }
}

use Test::Nginx::Socket::Lua::Stream $SkipReason ? (skip_all => $SkipReason) : ();
#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
no_long_string();
#master_on();
#workers(2);

no_shuffle();

run_tests();

__DATA__

=== TEST 1: initialize the fields in shdict
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        dogs:set("bah", 10502)
        local val = dogs:get("foo")
        ngx.say(val, " ", type(val))
        val = dogs:get("bah")
        ngx.say(val, " ", type(val))
    }
--- stream_response
32 number
10502 number
--- no_error_log
[error]



=== TEST 2: retrieve the fields in shdict after HUP reload
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        -- dogs:set("foo", 32)
        -- dogs:set("bah", 10502)

        local val = dogs:get("foo")
        ngx.say(val, " ", type(val))
        val = dogs:get("bah")
        ngx.say(val, " ", type(val))
    }
--- stream_response
32 number
10502 number
--- no_error_log
[error]
