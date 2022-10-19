# vim:set ft= ts=4 sw=4 et:

use t::Test;

repeat_each(2);

plan tests => repeat_each() * (4 * blocks());

run_tests();

__DATA__

=== TEST 1: continue using the obj when read timeout happens
--- global_config eval: $::GlobalConfig
--- server_config
        content_by_lua '
            local redis = require "resty.redis"
            local red = redis:new()

            local ok, err = red:connect("127.0.0.1", 1921);
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            red:set_timeout(100) -- 0.1 sec

            for i = 1, 2 do
                local data, err = red:get("foo")
                if not data then
                    ngx.say("failed to get: ", err)
                else
                    ngx.say("get: ", data);
                end
                ngx.sleep(0.1)
            end

            red:close()
        ';
--- tcp_listen: 1921
--- tcp_query eval
"*2\r
\$3\r
get\r
\$3\r
foo\r
"
--- tcp_reply eval
"\$5\r\nhello\r\n"
--- tcp_reply_delay: 150ms
--- response_body
failed to get: timeout
failed to get: closed
--- error_log
lua tcp socket read timed out
