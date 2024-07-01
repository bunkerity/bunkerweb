# vim:set ft= ts=4 sw=4 et:

use Test::Nginx::Socket::Lua;
use Cwd qw(cwd);

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

my $pwd = cwd();

$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';

our $HttpConfig = qq(
    lua_package_path "$pwd/t/lib/?.lua;$pwd/lib/?.lua;;";
    lua_package_cpath "/usr/local/openresty-debug/lualib/?.so;/usr/local/openresty/lualib/?.so;;";
    resolver '$ENV{TEST_NGINX_RESOLVER}';
);

no_long_string();

run_tests();

__DATA__

=== TEST 1: A records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("www.google.com", { qtype = r.TYPE_A })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[.*?"address":"(?:\d{1,3}\.){3}\d+".*?\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 2: CNAME records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("www.yahoo.com", { qtype = r.TYPE_CNAME })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[.*?"cname":"[-_a-z0-9.]+".*?\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 3: AAAA records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"
            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("www.google.com", { qtype = r.TYPE_AAAA })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[.*?"address":"[a-fA-F0-9]*(?::[a-fA-F0-9]*)+".*?\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 4: compress ipv6 addr
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local c = resolver.compress_ipv6_addr

            ngx.say(c("1080:0:0:0:8:800:200C:417A"))
            ngx.say(c("FF01:0:0:0:0:0:0:101"))
            ngx.say(c("0:0:0:0:0:0:0:1"))
            ngx.say(c("1:5:0:0:0:0:0:0"))
            ngx.say(c("7:25:0:0:0:3:0:0"))
            ngx.say(c("0:0:0:0:0:0:0:0"))
        ';
    }
--- request
GET /t
--- response_body
1080::8:800:200C:417A
FF01::101
::1
1:5::
7:25::3:0:0
::
--- no_error_log
[error]



=== TEST 5: A records (TCP)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:tcp_query("www.google.com", { qtype = r.TYPE_A })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[.*?"address":"(?:\d{1,3}\.){3}\d+".*?\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 6: MX records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("gmail.com", { qtype = r.TYPE_MX })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[\{.*?"preference":\d+,.*?"exchange":"[^"]+".*?\}\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 7: NS records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("google.com", { qtype = r.TYPE_NS })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[\{.*?"nsdname":"[^"]+".*?\}\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 8: TXT query (no ans)
--- SKIP
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("agentzh.org", { qtype = r.TYPE_TXT })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body
records: {}
--- no_error_log
[error]
--- timeout: 10



=== TEST 9: TXT query (with ans)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("gmail.com", { qtype = r.TYPE_TXT })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[\{.*?"txt":"v=spf\d+\s[^"]+".*?\}\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 10: PTR query
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("4.4.8.8.in-addr.arpa", { qtype = r.TYPE_PTR })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[\{.*?"ptrdname":"dns\.google".*?\}\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 11: domains with a trailing dot
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("www.google.com.", { qtype = r.TYPE_A })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[.*?"address":"(?:\d{1,3}\.){3}\d+".*?\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 12: domains with a leading dot
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query(".www.google.com", { qtype = r.TYPE_A })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body
failed to query: bad name
--- no_error_log
[error]



=== TEST 13: SRV records or XMPP
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("_xmpp-client._tcp.jabber.org", { qtype = r.TYPE_SRV })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[(?:{"class":1,"name":"_xmpp-client._tcp.jabber.org","port":\d+,"priority":\d+,"section":1,"target":"[\w.]+\.jabber.org","ttl":\d+,"type":33,"weight":\d+},?)+\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 14: SPF query (with ans)
SPF records are deprecated by RFC 7208 in favor of TXT records, and
linkedin.com has migrated to such TXT records.
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("linkedin.com", { qtype = r.TYPE_SPF })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body
records: []
--- no_error_log
[error]
--- no_check_leak



=== TEST 15: SPF query (no ans)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("agentzh.org", { qtype = r.TYPE_SPF })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body
records: []
--- no_error_log
[error]
--- timeout: 10



=== TEST 16: SPF query (as TXT with ans)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("linkedin.com", { qtype = r.TYPE_TXT })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            for i = 1, #ans do
                if string.find(ans[i].txt, "v=spf", nil, true) then
                    local ljson = require "ljson"
                    ngx.say("ans: ", ljson.encode(ans[i]))
                end
            end
        ';
    }
--- request
GET /t
--- response_body_like chop
^ans: \{.*?"txt":"v=spf\d+\s[^"]+".*?\}$
--- no_error_log
[error]
--- no_check_leak



=== TEST 17: generate arpa_str
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"
            local c = resolver.arpa_str
            ngx.say(c("1234:5678:abcd:ef99:1234:5678:abcd:ef99"))
            ngx.say(c("1080::8:800:200c:417a"))
            ngx.say(c("ff01::101"))
            ngx.say(c("::1"))
            ngx.say(c("::"))
            ngx.say(c("1::"))
            ngx.say(c("127.0.0.1"))
            ngx.say(c("251.252.253.254"))
        ';
    }
--- request
GET /t
--- response_body
9.9.f.e.d.c.b.a.8.7.6.5.4.3.2.1.9.9.f.e.d.c.b.a.8.7.6.5.4.3.2.1.ip6.arpa
a.7.1.4.c.0.0.2.0.0.8.0.8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.8.0.1.ip6.arpa
1.0.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.f.f.ip6.arpa
1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa
0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa
0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.ip6.arpa
1.0.0.127.in-addr.arpa
254.253.252.251.in-addr.arpa
--- no_error_log
[error]



=== TEST 18: SOA records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("www.google.com", { qtype = r.TYPE_SOA })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[(?:{"class":1,"expire":\d+,"minimum":\d+,"mname":"ns\d+\.google\.com","name":"google\.com","refresh":\d+,"retry":\d+,"rname":"dns-admin\.google\.com","section":2,"serial":\d+,"ttl":\d+,"type":6},?)+\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 19: RRTYPE larger than 255
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err = resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("comodo.com", { qtype = 257 })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[(?:{"class":1,"name":"comodo\.com","rdata":"[^"]+","section":1,"ttl":\d+,"type":257},?)+\]$
--- no_error_log
[error]
--- no_check_leak



=== TEST 20: SOA records
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resolver = require "resty.dns.resolver"

            local r, err =
                resolver:new{ nameservers = { "$TEST_NGINX_RESOLVER" } }
            if not r then
                ngx.say("failed to instantiate resolver: ", err)
                return
            end

            local ans, err = r:query("google.com", { qtype = r.TYPE_SOA })
            if not ans then
                ngx.say("failed to query: ", err)
                return
            end

            local ljson = require "ljson"
            ngx.say("records: ", ljson.encode(ans))
        ';
    }
--- request
GET /t
--- response_body_like chop
^records: \[.*?"name":"google.com".*?\]$
--- no_error_log
[error]
--- no_check_leak
