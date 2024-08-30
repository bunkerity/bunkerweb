-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http', 'stream')


local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local errmsg = base.get_errmsg_ptr()
local FFI_OK = base.FFI_OK
local FFI_ERROR = base.FFI_ERROR
local int_out = ffi.new("int[1]")
local get_request = base.get_request
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr

local error = error
local type = type
local tonumber = tonumber
local max = math.max

local subsystem = ngx.config.subsystem
local ngx_lua_ffi_balancer_set_current_peer
local ngx_lua_ffi_balancer_enable_keepalive
local ngx_lua_ffi_balancer_set_more_tries
local ngx_lua_ffi_balancer_get_last_failure
local ngx_lua_ffi_balancer_set_timeouts -- used by both stream and http
local ngx_lua_ffi_balancer_set_upstream_tls
local ngx_lua_ffi_balancer_bind_to_local_addr


if subsystem == 'http' then
    ffi.cdef[[
    int ngx_http_lua_ffi_balancer_set_current_peer(ngx_http_request_t *r,
        const unsigned char *addr, size_t addr_len, int port,
        const unsigned char *host, ssize_t host_len,
        char **err);

    int ngx_http_lua_ffi_balancer_enable_keepalive(ngx_http_request_t *r,
        unsigned long timeout, unsigned int max_requests, char **err);

    int ngx_http_lua_ffi_balancer_set_more_tries(ngx_http_request_t *r,
        int count, char **err);

    int ngx_http_lua_ffi_balancer_get_last_failure(ngx_http_request_t *r,
        int *status, char **err);

    int ngx_http_lua_ffi_balancer_set_timeouts(ngx_http_request_t *r,
        long connect_timeout, long send_timeout,
        long read_timeout, char **err);

    int ngx_http_lua_ffi_balancer_recreate_request(ngx_http_request_t *r,
        char **err);

    int ngx_http_lua_ffi_balancer_set_upstream_tls(ngx_http_request_t *r,
        int on, char **err);

    int ngx_http_lua_ffi_balancer_bind_to_local_addr(ngx_http_request_t *r,
        const u_char *addr, size_t addr_len,
        u_char *errbuf, size_t *errbuf_size);
    ]]

    ngx_lua_ffi_balancer_set_current_peer =
        C.ngx_http_lua_ffi_balancer_set_current_peer

    ngx_lua_ffi_balancer_enable_keepalive =
        C.ngx_http_lua_ffi_balancer_enable_keepalive

    ngx_lua_ffi_balancer_set_more_tries =
        C.ngx_http_lua_ffi_balancer_set_more_tries

    ngx_lua_ffi_balancer_get_last_failure =
        C.ngx_http_lua_ffi_balancer_get_last_failure

    ngx_lua_ffi_balancer_set_timeouts =
        C.ngx_http_lua_ffi_balancer_set_timeouts

    ngx_lua_ffi_balancer_set_upstream_tls =
        C.ngx_http_lua_ffi_balancer_set_upstream_tls

    ngx_lua_ffi_balancer_bind_to_local_addr =
        C.ngx_http_lua_ffi_balancer_bind_to_local_addr

elseif subsystem == 'stream' then
    ffi.cdef[[
    int ngx_stream_lua_ffi_balancer_set_current_peer(
        ngx_stream_lua_request_t *r,
        const unsigned char *addr, size_t addr_len, int port, char **err);

    int ngx_stream_lua_ffi_balancer_set_more_tries(ngx_stream_lua_request_t *r,
        int count, char **err);

    int ngx_stream_lua_ffi_balancer_get_last_failure(
        ngx_stream_lua_request_t *r, int *status, char **err);

    int ngx_stream_lua_ffi_balancer_set_timeouts(ngx_stream_lua_request_t *r,
        long connect_timeout, long timeout, char **err);

    int ngx_stream_lua_ffi_balancer_bind_to_local_addr(
        ngx_stream_lua_request_t *r, const char *addr, size_t addr_len,
        char *errbuf, size_t *errbuf_size);
    ]]

    ngx_lua_ffi_balancer_set_current_peer =
        C.ngx_stream_lua_ffi_balancer_set_current_peer

    ngx_lua_ffi_balancer_set_more_tries =
        C.ngx_stream_lua_ffi_balancer_set_more_tries

    ngx_lua_ffi_balancer_get_last_failure =
        C.ngx_stream_lua_ffi_balancer_get_last_failure

    local ngx_stream_lua_ffi_balancer_set_timeouts =
        C.ngx_stream_lua_ffi_balancer_set_timeouts

    ngx_lua_ffi_balancer_set_timeouts =
        function(r, connect_timeout, send_timeout, read_timeout, err)
            local timeout = max(send_timeout, read_timeout)

            return ngx_stream_lua_ffi_balancer_set_timeouts(r, connect_timeout,
                                                            timeout, err)
        end

    ngx_lua_ffi_balancer_bind_to_local_addr =
        C.ngx_stream_lua_ffi_balancer_bind_to_local_addr

else
    error("unknown subsystem: " .. subsystem)
end

local DEFAULT_KEEPALIVE_IDLE_TIMEOUT = 60000
local DEFAULT_KEEPALIVE_MAX_REQUESTS = 100

local peer_state_names = {
    [1] = "keepalive",
    [2] = "next",
    [4] = "failed",
}


local _M = { version = base.version }

if subsystem == "http" then
    function _M.set_current_peer(addr, port, host)
        local r = get_request()
        if not r then
            error("no request found")
        end

        if not port then
            port = 0
        elseif type(port) ~= "number" then
            port = tonumber(port)
        end

        if host ~= nil and type(host) ~= "string" then
            error("bad argument #3 to 'set_current_peer' "
                  .. "(string expected, got " .. type(host) .. ")")
        end

        local rc = ngx_lua_ffi_balancer_set_current_peer(r, addr, #addr,
                                                         port,
                                                         host,
                                                         host and #host or 0,
                                                         errmsg)
        if rc == FFI_OK then
            return true
        end

        return nil, ffi_str(errmsg[0])
    end
else
    function _M.set_current_peer(addr, port, host)
        local r = get_request()
        if not r then
            error("no request found")
        end

        if not port then
            port = 0
        elseif type(port) ~= "number" then
            port = tonumber(port)
        end

        if host ~= nil then
            error("bad argument #3 to 'set_current_peer' ('host' not yet " ..
                  "implemented in " .. subsystem .. " subsystem)", 2)
        end

        local rc = ngx_lua_ffi_balancer_set_current_peer(r, addr, #addr,
                                                         port,
                                                         errmsg)
        if rc == FFI_OK then
            return true
        end

        return nil, ffi_str(errmsg[0])
    end
end

if subsystem == "http" then
    function _M.enable_keepalive(idle_timeout, max_requests)
        local r = get_request()
        if not r then
            error("no request found")
        end

        if not idle_timeout then
            idle_timeout = DEFAULT_KEEPALIVE_IDLE_TIMEOUT

        elseif type(idle_timeout) ~= "number" then
            error("bad argument #1 to 'enable_keepalive' " ..
                  "(number expected, got " .. type(idle_timeout) .. ")", 2)

        elseif idle_timeout < 0 then
            error("bad argument #1 to 'enable_keepalive' (expected >= 0)", 2)

        else
            idle_timeout = idle_timeout * 1000
        end

        if not max_requests then
            max_requests = DEFAULT_KEEPALIVE_MAX_REQUESTS

        elseif type(max_requests) ~= "number" then
            error("bad argument #2 to 'enable_keepalive' " ..
                  "(number expected, got " .. type(max_requests) .. ")", 2)

        elseif max_requests < 0 then
            error("bad argument #2 to 'enable_keepalive' (expected >= 0)", 2)
        end

        local rc = ngx_lua_ffi_balancer_enable_keepalive(r, idle_timeout,
                                                         max_requests, errmsg)
        if rc == FFI_OK then
            return true
        end

        return nil, ffi_str(errmsg[0])
    end

else
    function _M.enable_keepalive()
        error("'enable_keepalive' not yet implemented in " .. subsystem ..
              " subsystem", 2)
    end
end

function _M.set_more_tries(count)
    local r = get_request()
    if not r then
        error("no request found")
    end

    local rc = ngx_lua_ffi_balancer_set_more_tries(r, count, errmsg)
    if rc == FFI_OK then
        if errmsg[0] == nil then
            return true
        end
        return true, ffi_str(errmsg[0])  -- return the warning
    end

    return nil, ffi_str(errmsg[0])
end


function _M.get_last_failure()
    local r = get_request()
    if not r then
        error("no request found")
    end

    local state = ngx_lua_ffi_balancer_get_last_failure(r, int_out, errmsg)

    if state == 0 then
        return nil
    end

    if state == FFI_ERROR then
        return nil, nil, ffi_str(errmsg[0])
    end

    return peer_state_names[state] or "unknown", int_out[0]
end


function _M.set_timeouts(connect_timeout, send_timeout, read_timeout)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if not connect_timeout then
        connect_timeout = 0
    elseif type(connect_timeout) ~= "number" or connect_timeout <= 0 then
        error("bad connect timeout", 2)
    else
        connect_timeout = connect_timeout * 1000
    end

    if not send_timeout then
        send_timeout = 0
    elseif type(send_timeout) ~= "number" or send_timeout <= 0 then
        error("bad send timeout", 2)
    else
        send_timeout = send_timeout * 1000
    end

    if not read_timeout then
        read_timeout = 0
    elseif type(read_timeout) ~= "number" or read_timeout <= 0 then
        error("bad read timeout", 2)
    else
        read_timeout = read_timeout * 1000
    end

    local rc

    rc = ngx_lua_ffi_balancer_set_timeouts(r, connect_timeout,
                                           send_timeout, read_timeout,
                                           errmsg)

    if rc == FFI_OK then
        return true
    end

    return false, ffi_str(errmsg[0])
end


if subsystem == 'http' then
    function _M.recreate_request()
        local r = get_request()
        if not r then
            error("no request found")
        end

        local rc = C.ngx_http_lua_ffi_balancer_recreate_request(r, errmsg)
        if rc == FFI_OK then
            return true
        end

        if errmsg[0] ~= nil then
            return nil, ffi_str(errmsg[0])
        end

        return nil, "failed to recreate the upstream request"
    end


    function _M.set_upstream_tls(on)
        local r = get_request()
        if not r then
            return error("no request found")
        end

        local rc

        if on == 0 or on == false then
            on = 0
        else
            on = 1
        end

        rc = ngx_lua_ffi_balancer_set_upstream_tls(r, on, errmsg);
        if rc == FFI_OK then
            return true
        end

        return nil, ffi_str(errmsg[0])
    end
end

function _M.bind_to_local_addr(addr)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if type(addr) ~= "string" then
        error("bad argument #1 to 'bind_to_local_addr' "
              .. "(string expected, got " .. type(addr) .. ")")
    end

    local errbuf_size = 1024
    local errbuf = get_string_buf(errbuf_size)
    local sizep = get_size_ptr()
    sizep[0] = errbuf_size
    local rc = ngx_lua_ffi_balancer_bind_to_local_addr(r, addr, #addr,
                                                       errbuf,
                                                       sizep)
    if rc == FFI_OK then
        return true
    end

    return nil, ffi_str(errbuf, sizep[0])
end


return _M
