local _M = {}


local run_lua_with_graceful_shutdown
do
    local function set_up_ngx_conf(dir, code)
        local conf = [[
            error_log stderr error;
            master_process off;
            daemon off;
            events {
                worker_connections 64;
            }
            http {
                init_worker_by_lua_block {
                    ngx.timer.at(0, function ()
        ]] .. code .. [[
                        require("ngx.process").signal_graceful_exit()
                    end)
                }
            }
        ]]

        assert(os.execute("mkdir -p " .. dir .. "/logs"))

        local conf_file = dir .. "/nginx.conf"
        local f, err = io.open(conf_file, "w")
        if not f then
            ngx.log(ngx.ERR, err)
            return
        end

        assert(f:write(conf))
        f:close()

        return conf_file
    end

    local function get_ngx_bin_path()
        local ffi = require "ffi"
        ffi.cdef[[char **ngx_argv;]]
        return ffi.string(ffi.C.ngx_argv[0])
    end

    function run_lua_with_graceful_shutdown(dir, code)
        local ngx_pipe = require "ngx.pipe"
        local conf_file = set_up_ngx_conf(dir, code)
        local nginx = get_ngx_bin_path()

        local cmd = nginx .. " -p " .. dir .. " -c " .. conf_file
        return ngx_pipe.spawn(cmd)
    end
end
_M.run_lua_with_graceful_shutdown = run_lua_with_graceful_shutdown


return _M
