# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib '.';
use t::TestCore;

master_process_enabled(1);

repeat_each(1);

plan tests => repeat_each() * (blocks() * 5);


$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = $t::TestCore::lua_package_path;
$ENV{TEST_NGINX_RANDOM_PORT} = Test::Nginx::Util::server_port();

run_tests();

__DATA__

=== TEST 1: specify connections to enable_privileged_agent
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent(10)
        if not ok then
            ngx.log(ngx.ERR, "enable_privileged_agent failed: ", err)
        end
    }

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local typ = (require "ngx.process").type()

        if typ == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", typ)
            ngx.timer.at(0, function()
                local tcpsock = ngx.socket.tcp()
                local ok, err = tcpsock:connect("127.0.0.1", $TEST_NGINX_RANDOM_PORT)

                if ok then
                    ngx.log(ngx.INFO, "connect ok ")
                else
                    ngx.log(ngx.INFO, "connect failed " .. tostring(err))
                end
            end)
        end
    }
--- config
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.1)
            local typ = require "ngx.process".type()
            ngx.say("type: ", typ)
        }
    }
--- request
GET /t
--- response_body
type: worker
--- error_log
connect ok
--- no_error_log
connect failed
enable_privileged_agent failed
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2



=== TEST 2: connections exceed limit
the real connections you can create is always less than you set.
timer will take fake connections.
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent(10)
        if not ok then
            ngx.log(ngx.ERR, "enable_privileged_agent failed: ", err)
        end
    }

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local typ = (require "ngx.process").type()

        if typ == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", typ)

            ngx.timer.at(0, function()

                for i = 1, 10 do
                    local tcpsock = ngx.socket.tcp()
                    local ok, err = tcpsock:connect("127.0.0.1", $TEST_NGINX_RANDOM_PORT)

                    if ok then
                        ngx.log(ngx.INFO, "connect ok ")
                    else
                        ngx.log(ngx.INFO, "connect failed " .. tostring(err))
                    end
                end

            end)
        end
    }
--- config
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.1)
            local typ = require "ngx.process".type()
            ngx.say("type: ", typ)
        }
    }
--- request
GET /t
--- response_body
type: worker
--- error_log
connect failed
worker_connections are not enough
--- no_error_log
enable_privileged_agent failed
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2



=== TEST 3: enable_privileged_agent with bad connections
connections < 0
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent(-1)
        if not ok then
            ngx.log(ngx.ERR, "enable_privileged_agent failed: ", err)
        end
    }

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local typ = (require "ngx.process").type()

        if typ == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", typ)

            ngx.timer.at(0, function()

                for i = 1, 10 do
                    local tcpsock = ngx.socket.tcp()
                    local ok, err = tcpsock:connect("127.0.0.1", $TEST_NGINX_RANDOM_PORT)

                    if ok then
                        ngx.log(ngx.INFO, "connect ok ")
                    else
                        ngx.log(ngx.INFO, "connect failed " .. tostring(err))
                    end
                end

            end)
        end
    }
--- config
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.1)
            local typ = require "ngx.process".type()
            ngx.say("type: ", typ)
        }
    }
--- request
GET /t
--- response_body
type: worker
--- error_log
enable_privileged_agent failed: bad 'connections' argument
--- no_error_log
connect ok
connect failed
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2



=== TEST 4: enable_privileged_agent with bad connections
connections is not a number
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent("10")
        if not ok then
            ngx.log(ngx.ERR, "enable_privileged_agent failed: ", err)
        end
    }

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local typ = (require "ngx.process").type()

        if typ == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", typ)

            ngx.timer.at(0, function()

                for i = 1, 10 do
                    local tcpsock = ngx.socket.tcp()
                    local ok, err = tcpsock:connect("127.0.0.1", $TEST_NGINX_RANDOM_PORT)

                    if ok then
                        ngx.log(ngx.INFO, "connect ok ")
                    else
                        ngx.log(ngx.INFO, "connect failed " .. tostring(err))
                    end
                end

            end)
        end
    }
--- config
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.1)
            local typ = require "ngx.process".type()
            ngx.say("type: ", typ)
        }
    }
--- request
GET /t
--- response_body
type: worker
--- error_log
enable_privileged_agent failed: bad 'connections' argument
--- no_error_log
connect ok
connect failed
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2



=== TEST 5: enable_privileged_agent with bad connections
connections = 0
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    init_by_lua_block {
        local process = require "ngx.process"
        local ok, err = process.enable_privileged_agent(0)
        if not ok then
            ngx.log(ngx.ERR, "enable_privileged_agent failed: ", err)
        end
    }

    init_worker_by_lua_block {
        local base = require "resty.core.base"
        local typ = (require "ngx.process").type()

        if typ == "privileged agent" then
            ngx.log(ngx.WARN, "process type: ", typ)

            ngx.timer.at(0, function()

                for i = 1, 10 do
                    local tcpsock = ngx.socket.tcp()
                    local ok, err = tcpsock:connect("127.0.0.1", $TEST_NGINX_RANDOM_PORT)

                    if ok then
                        ngx.log(ngx.INFO, "connect ok ")
                    else
                        ngx.log(ngx.INFO, "connect failed " .. tostring(err))
                    end
                end

            end)
        end
    }
--- config
    location = /t {
        content_by_lua_block {
            ngx.sleep(0.1)
            local typ = require "ngx.process".type()
            ngx.say("type: ", typ)
        }
    }
--- request
GET /t
--- response_body
type: worker
--- error_log
0 worker_connection is not enough, privileged agent process cannot be spawned
--- no_error_log
process type: privileged agent
connect ok
--- skip_nginx: 5: < 1.11.2
--- wait: 0.2
