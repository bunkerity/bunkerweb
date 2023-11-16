# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
log_level('debug');

repeat_each(3);

plan tests => repeat_each() * (blocks() * 3);

our $HtmlDir = html_dir;
#warn $html_dir;

$ENV{TEST_NGINX_HTML_DIR} = $HtmlDir;
$ENV{TEST_NGINX_REDIS_PORT} ||= 6379;

#no_diff();
#no_long_string();

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';

#no_shuffle();
no_long_string();

sub read_file {
    my $infile = shift;
    open my $in, $infile
        or die "cannot open $infile for reading: $!";
    my $cert = do { local $/; <$in> };
    close $in;
    $cert;
}

our $TestCertificate = read_file("t/cert/test.crt");
our $TestCertificateKey = read_file("t/cert/test.key");

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        package.loaded.foo = nil;
        local foo = require "foo";
        foo.hi()
    }
--- user_files
>>> foo.lua
module(..., package.seeall);

function foo ()
    return 1
    return 2
end
--- stream_response
--- error_log
error loading module 'foo' from file



=== TEST 2: print lua empty strings
--- stream_server_config
    content_by_lua_block { ngx.print("") ngx.flush() ngx.print("Hi") }
--- stream_response chop
Hi
--- no_error_log
[error]



=== TEST 3: say lua empty strings
--- stream_server_config
    content_by_lua_block { ngx.say("") ngx.flush() ngx.print("Hi") }
--- stream_response eval
"
Hi"
--- no_error_log
[error]



=== TEST 4: lua_code_cache off + setkeepalive
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local test = require "test"
        local port = $TEST_NGINX_REDIS_PORT
        test.go(port)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

function go(port)
    local sock = ngx.socket.tcp()
    local sock2 = ngx.socket.tcp()

    sock:settimeout(1000)
    sock2:settimeout(6000000)

    local ok, err = sock:connect("127.0.0.1", port)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    local ok, err = sock2:connect("127.0.0.1", port)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    local ok, err = sock:setkeepalive(100, 100)
    if not ok then
        ngx.say("failed to set reusable: ", err)
    end

    local ok, err = sock2:setkeepalive(200, 100)
    if not ok then
        ngx.say("failed to set reusable: ", err)
    end

    ngx.say("done")
end
--- stap2
F(ngx_close_connection) {
    println("=== close connection")
    print_ubacktrace()
}
--- stap_out2
--- stream_response
done
--- wait: 0.5
--- no_error_log
[error]



=== TEST 5: .lua file of exactly N*1024 bytes (github issue #385)
--- stream_server_config
    content_by_lua_file html/a.lua;

--- user_files eval
my $s = "ngx.say('ok')\n";
">>> a.lua\n" . (" " x (8192 - length($s))) . $s;

--- stream_response
ok
--- no_error_log
[error]



=== TEST 6: tcp: nginx crash when resolve an not exist domain in ngx.thread.spawn
https://github.com/openresty/lua-nginx-module/issues/1915
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local function tcp(host, port)
            local sock = ngx.socket.tcp()
            local ok,err = sock:connect(host, port)
            if not ok then
                ngx.log(ngx.WARN, "failed: ", err)
                sock:close()
                return false
            end

            sock:close()
            return true
        end

        local host = "notexistdomain.openresty.org"
        local port = 80

        local threads = {}
        for i = 1, 3 do
            threads[i] = ngx.thread.spawn(tcp, host, port)
        end

        local ok, res = ngx.thread.wait(threads[1],threads[2],threads[3])
        if not ok then
            ngx.say("failed to wait thread")
            return
        end

        ngx.say("res: ", res)

        for i = 1, 3 do
            ngx.thread.kill(threads[i])
        end
    }

--- request
GET /t
--- response_body
res: false
--- error_log
notexistdomain.openresty.org could not be resolved



=== TEST 7: domain exists with tcp socket
https://github.com/openresty/lua-nginx-module/issues/1915
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local function tcp(host, port)
            local sock = ngx.socket.tcp()
            local ok,err = sock:connect(host, port)
            if not ok then
                ngx.log(ngx.WARN, "failed: ", err)
                sock:close()
                return false
            end

            sock:close()
            return true
        end

        local host = "www.openresty.org"
        local port = 80

        local threads = {}
        for i = 1, 3 do
            threads[i] = ngx.thread.spawn(tcp, host, port)
        end

        local ok, res = ngx.thread.wait(threads[1],threads[2],threads[3])
        if not ok then
            ngx.say("failed to wait thread")
            return
        end

        ngx.say("res: ", res)

        for i = 1, 3 do
            ngx.thread.kill(threads[i])
        end
    }

--- request
GET /t
--- response_body
res: true
--- no_error_log
[error]



=== TEST 8: domain exists with udp socket
https://github.com/openresty/lua-nginx-module/issues/1915
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local function udp(host, port)
            local sock = ngx.socket.udp()
            local ok,err = sock:setpeername(host, port)
            if not ok then
                ngx.log(ngx.WARN, "failed: ", err)
                sock:close()
                return false
            end

            sock:close()
            return true
        end

        local host = "notexistdomain.openresty.org"
        local port = 80

        local threads = {}
        for i = 1, 3 do
            threads[i] = ngx.thread.spawn(udp, host, port)
        end

        local ok, res = ngx.thread.wait(threads[1],threads[2],threads[3])
        if not ok then
            ngx.say("failed to wait thread")
            return
        end

        ngx.say("res: ", res)

        for i = 1, 3 do
            ngx.thread.kill(threads[i])
        end
    }

--- request
GET /t
--- response_body
res: false
--- error_log
notexistdomain.openresty.org could not be resolved



=== TEST 9: udp: nginx crash when resolve an not exist domain in ngx.thread.spawn
https://github.com/openresty/lua-nginx-module/issues/1915
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local function udp(host, port)
            local sock = ngx.socket.udp()
            local ok,err = sock:setpeername(host, port)
            if not ok then
                ngx.log(ngx.WARN, "failed: ", err)
                sock:close()
                return false
            end

            sock:close()
            return true
        end

        local host = "www.openresty.org"
        local port = 80

        local threads = {}
        for i = 1, 3 do
            threads[i] = ngx.thread.spawn(udp, host, port)
        end

        local ok, res = ngx.thread.wait(threads[1],threads[2],threads[3])
        if not ok then
            ngx.say("failed to wait thread")
            return
        end

        ngx.say("res: ", res)

        for i = 1, 3 do
            ngx.thread.kill(threads[i])
        end
    }

--- request
GET /t
--- response_body
res: true
--- no_error_log
[error]
