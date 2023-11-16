# vim:set ft= ts=4 sw=4 et fdm=marker:

use t::IP 'no_plan';

repeat_each(1);
run_tests();


__DATA__

=== TEST 1: ipv4 address
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "127.0.0.1",
                "127.0.0.2",
                "192.168.0.0/16",
            })

            ngx.say(ip:match("127.0.0.1"))
            ngx.say(ip:match("127.0.0.2"))
            ngx.say(ip:match("127.0.0.3"))
            ngx.say(ip:match("192.168.1.1"))
            ngx.say(ip:match("192.168.1.100"))
            ngx.say(ip:match("192.100.1.100"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
true
false
true
true
false



=== TEST 2: ipv6 address
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "::1",
                "fe80::/32",
            })

            ngx.say(ip:match("::1"))
            ngx.say(ip:match("::2"))
            ngx.say(ip:match("fe80::"))
            ngx.say(ip:match("fe80:1::"))

            ngx.say(ip:match("127.0.0.1"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
false
true
false
false



=== TEST 3: invalid ip address
--- config
    location /t {
        content_by_lua_block {
            local ip, err = require("resty.ipmatcher").new({
                "127.0.0.ffff",
            })

            ngx.say("ip: ", ip)
            ngx.say("err:", err)
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
ip: nil
err:invalid ip address: 127.0.0.ffff



=== TEST 4: invalid ip address
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "127.0.0.1",
            })

            local ok, err = ip:match("127.0.0.ffff")
            ngx.say("ok: ", ok)
            ngx.say("err:", err)
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
ok: false
err:invalid ip address, not ipv4 and ipv6



=== TEST 5: ipv6 address (short mask)
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "fe80::/8",
            })

            ngx.say(ip:match("fe81::"))
            ngx.say(ip:match("ff80::"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
false



=== TEST 6: parse ipv6 address
--- config
    location /t {
        content_by_lua_block {
            local cases = {
                {ip = "127.0.0.ffff"},
                {ip = ""},
                {ip = "["},
                {ip = "[]"},
                {ip = "[:1:]"},
                {ip = "[::1x"},
                {ip = "127.0.0.1"},
            }
            for _, case in ipairs(cases) do
                local valid = require("resty.ipmatcher").parse_ipv6(case.ip)
                if valid then
                    ngx.log(ngx.ERR, "expect invalid IPv6 ", case.ip)
                end
            end

            local cases = {
                {ip = "::1"},
                {ip = "[::1]"},
                {ip = "ff80::"},
            }
            for _, case in ipairs(cases) do
                local valid = require("resty.ipmatcher").parse_ipv6(case.ip)
                if not valid then
                    ngx.log(ngx.ERR, "expect IPv6 ", case.ip)
                end
            end
        }
    }
--- request
GET /t
--- no_error_log
[error]



=== TEST 7: match binary ip
This test requires building Nginx with --with-http_realip_module
--- config
    location /foo {
        set_real_ip_from  127.0.0.1;
        content_by_lua_block {
            ngx.log(ngx.INFO, ngx.var.http_x_real_ip, " ", ngx.var.binary_remote_addr)
            ngx.print(ngx.var.binary_remote_addr)
        }
    }
    location /t {
        content_by_lua_block {
            local function get_bin_ip(ip)
                local sock = ngx.socket.tcp()
                sock:settimeout(500)

                local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
                if not ok then
                    ngx.log(ngx.ERR, "failed to connect: ", err)
                    return
                end

                local req = "GET /foo HTTP/1.0\r\nHost: test.com\r\nConnection: close\r\nX-Real-IP:" .. ip .. "\r\n\r\n"
                local bytes, err = sock:send(req)
                if not bytes then
                    ngx.log(ngx.ERR, "failed to send http request: ", err)
                    return
                end

                -- skip http header
                while true do
                    local data, err, _ = sock:receive('*l')
                    if err then
                        ngx.log(ngx.ERR, 'unexpected error occurs when receiving http head: ' .. err)
                        return
                    end
                    if #data == 0 then -- read last line of head
                        break
                    end
                end

                local data, err = sock:receive('*a')
                sock:close()
                if not data then
                    ngx.log(ngx.ERR, "failed to receive body: ", err)
                end
                return data
            end

            local ip = require("resty.ipmatcher").new({
                "127.0.0.1",
                "192.168.0.0/16",
                "::1",
                "fe80::/8",
            })
            local cases = {
                {ip = "127.0.0.1", matched = true},
                {ip = "127.0.0.2", matched = false},
                {ip = "192.168.0.22", matched = true},
                {ip = "182.168.0.22", matched = false},
                {ip = "::1", matched = true},
                {ip = "::2", matched = false},
                {ip = "fe80::1", matched = true},
            }
            for _, case in ipairs(cases) do
                local res = ip:match_bin(get_bin_ip(case.ip))
                if res ~= case.matched then
                    ngx.say("unexpected result for ", case.ip)
                end
            end
            ngx.say("ok")
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
ok



=== TEST 8: zero mask
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "::/0",
                "0.0.0.0/0",
            })

            ngx.say(ip:match("127.0.0.1"))
            ngx.say(ip:match("0.0.0.0"))
            ngx.say(ip:match("fe81::"))
            ngx.say(ip:match("ff80::"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
true
true
true



=== TEST 9: ipv6 special notation
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            })
            ngx.say(ip:match("2001:0db8:85a3:0000:0000:8a2e:0370:7334"))
            -- zero in some occasions can be omitted
            ngx.say(ip:match("2001:db8:85a3:0:0:8a2e:370:7334"))
            ngx.say(ip:match("2001:db8:85a3::8a2e:370:7334"))

            local ip = require("resty.ipmatcher").new({
                "::ffff:192.0.2.128",
            })
            ngx.say(ip:match("::ffff:192.0.2.128"))
            -- ipv4-mapped address
            ngx.say(ip:match("::ffff:c000:0280"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
true
true
true
true



=== TEST 10: match with new_with_value
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new_with_value({
                ["127.0.0.1"] = 1,
                ["192.168.0.0/16"] = "2",
                ["::1"] = 3,
                ["fe80::/32"] = {value = 4},
                ["fe81::/32"] = false,
            })

            ngx.say(ip:match("127.0.0.1"))
            ngx.say(ip:match("127.0.0.2"))
            ngx.say(ip:match("192.168.1.1"))
            ngx.say(ip:match("192.168.1.100"))
            ngx.say(ip:match("192.100.1.100"))
            ngx.say(ip:match("::1"))
            ngx.say(ip:match("::2"))
            ngx.say(ip:match("fe80::").value)
            ngx.say(ip:match("fe80:1::"))
            ngx.say(ip:match("fe81::"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
1
false
2
2
false
3
false
4
false
false



=== TEST 11: new_with_value and zero mask
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new_with_value({
                ["::/0"] = 1,
                ["0.0.0.0/0"] = 2,
            })

            ngx.say(ip:match("127.0.0.1"))
            ngx.say(ip:match("0.0.0.0"))
            ngx.say(ip:match("fe81::"))
            ngx.say(ip:match("ff80::"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
2
2
1
1



=== TEST 12: bug: ipv4 address overrided with the same mask
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                "192.168.0.0/16",
                "192.0.0.0/16",
            })

            ngx.say(ip:match("192.168.1.1"))
            ngx.say(ip:match("192.0.1.100"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
true



=== TEST 13: bug fixing: same ipv6 prefix with the same mask
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new({
                '2409:8928:6a00::/39',
                '2409:8928:a000::/39', -- 2409:8928:a000:: - 2409:8928:a1ff:ffff:ffff:ffff:ffff:ffff
            })

            ngx.say(ip:match("2409:8928:6a00:2a57:1:1:d823:4521"))
            ngx.say(ip:match("2409:8928:6a01::"))
            ngx.say(ip:match("2409:8928:a0f8:2a57:1:1:d823:4521"))
            ngx.say(ip:match("2409:8928:a100::"))
            ngx.say(ip:match("2409:8928:a200::"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
true
true
true
true
false



=== TEST 14: accurate match with new_with_value
--- config
    location /t {
        content_by_lua_block {
            local ip = require("resty.ipmatcher").new_with_value({
                ["192.168.1.1/24"] = "level3",
                ["192.168.1.1/16"] = "level2",
                ["192.168.1.1/8"] = "level1",
            })

            ngx.say(ip:match("192.168.1.2"))
            ngx.say(ip:match("192.168.2.2"))
            ngx.say(ip:match("192.2.2.2"))

            local ip = require("resty.ipmatcher").new_with_value({
                ["192.168.1.1/16"] = "level2",
                ["192.168.1.1/8"] = "level1",
                ["192.168.1.1/24"] = "level3",
            })

            ngx.say(ip:match("192.168.1.2"))
            ngx.say(ip:match("192.168.2.2"))
            ngx.say(ip:match("192.2.2.2"))

            local ip = require("resty.ipmatcher").new_with_value({
                ["192.168.1.1/8"] = "level1",
                ["192.168.1.1/16"] = "level2",
                ["192.168.1.1/24"] = "level3",
            })

            ngx.say(ip:match("192.168.1.2"))
            ngx.say(ip:match("192.168.2.2"))
            ngx.say(ip:match("192.2.2.2"))
        }
    }
--- request
GET /t
--- no_error_log
[error]
--- response_body
level3
level2
level1
level3
level2
level1
level3
level2
level1
