# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2);

no_long_string();
run_tests();

__DATA__

=== TEST 1: set_current_peer: NYI 'opts' argument
--- stream_config
    upstream backend {
        server 127.0.0.1:12345;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local pok, perr = pcall(b.set_current_peer, "127.0.0.3", 12345, "abc")
            if not pok then
                ngx.log(ngx.ERR, perr)
            end
        }
    }
--- stream_server_config
    proxy_pass backend;
--- error_log eval
qr/balancer_by_lua:\d+: bad argument #3 to 'set_current_peer' \('host' not yet implemented in stream subsystem\)/



=== TEST 2: enable_keepalive: NYI
--- stream_config
    upstream backend {
        server 127.0.0.1:12345;

        balancer_by_lua_block {
            local b = require "ngx.balancer"

            local pok, perr = pcall(b.enable_keepalive)
            if not pok then
                ngx.log(ngx.ERR, perr)
            end
        }
    }
--- stream_server_config
    proxy_pass backend;
--- error_log eval
qr/balancer_by_lua:\d+: 'enable_keepalive' not yet implemented in stream subsystem/
