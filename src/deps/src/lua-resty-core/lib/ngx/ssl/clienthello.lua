-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http', 'stream')


local ffi = require "ffi"
local bit  = require "bit"
local bor = bit.bor
local C = ffi.C
local ffi_str = ffi.string
local get_request = base.get_request
local error = error
local errmsg = base.get_errmsg_ptr()
local get_size_ptr = base.get_size_ptr
local FFI_OK = base.FFI_OK
local subsystem = ngx.config.subsystem
local ngx_phase = ngx.get_phase
local byte = string.byte
local lshift = bit.lshift
local table_insert = table.insert


local ngx_lua_ffi_ssl_get_client_hello_server_name
local ngx_lua_ffi_ssl_get_client_hello_ext
local ngx_lua_ffi_ssl_set_protocols


if subsystem == 'http' then
    ffi.cdef[[
    int ngx_http_lua_ffi_ssl_get_client_hello_server_name(ngx_http_request_t *r,
        const char **name, size_t *namelen, char **err);

    int ngx_http_lua_ffi_ssl_get_client_hello_ext(ngx_http_request_t *r,
        unsigned int type, const unsigned char **out, size_t *outlen,
        char **err);

    int ngx_http_lua_ffi_ssl_set_protocols(ngx_http_request_t *r,
        int protocols, char **err);
    ]]

    ngx_lua_ffi_ssl_get_client_hello_server_name =
        C.ngx_http_lua_ffi_ssl_get_client_hello_server_name
    ngx_lua_ffi_ssl_get_client_hello_ext =
        C.ngx_http_lua_ffi_ssl_get_client_hello_ext
    ngx_lua_ffi_ssl_set_protocols = C.ngx_http_lua_ffi_ssl_set_protocols

elseif subsystem == 'stream' then
    ffi.cdef[[
    int ngx_stream_lua_ffi_ssl_get_client_hello_server_name(
        ngx_stream_lua_request_t *r, const char **name, size_t *namelen,
        char **err);

    int ngx_stream_lua_ffi_ssl_get_client_hello_ext(
        ngx_stream_lua_request_t *r, unsigned int type,
        const unsigned char **out, size_t *outlen, char **err);

    int ngx_stream_lua_ffi_ssl_set_protocols(ngx_stream_lua_request_t *r,
        int protocols, char **err);
    ]]

    ngx_lua_ffi_ssl_get_client_hello_server_name =
        C.ngx_stream_lua_ffi_ssl_get_client_hello_server_name
    ngx_lua_ffi_ssl_get_client_hello_ext =
        C.ngx_stream_lua_ffi_ssl_get_client_hello_ext
    ngx_lua_ffi_ssl_set_protocols = C.ngx_stream_lua_ffi_ssl_set_protocols
end


local _M = { version = base.version }


local ccharpp = ffi.new("const char*[1]")
local cucharpp = ffi.new("const unsigned char*[1]")


-- return server_name, err
function _M.get_client_hello_server_name()
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "ssl_client_hello" then
        error("API disabled in the current context")
    end

    local sizep = get_size_ptr()

    local rc = ngx_lua_ffi_ssl_get_client_hello_server_name(r, ccharpp, sizep,
                errmsg)
    if rc == FFI_OK then
        return ffi_str(ccharpp[0], sizep[0])
    end

    -- NGX_DECLINED: no sni extension
    if rc == -5 then
        return nil
    end

    return nil, ffi_str(errmsg[0])
end


-- return ext, err
function _M.get_client_hello_ext(ext_type)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "ssl_client_hello" then
        error("API disabled in the current context")
    end

    local sizep = get_size_ptr()

    local rc = ngx_lua_ffi_ssl_get_client_hello_ext(r, ext_type, cucharpp,
                                                    sizep, errmsg)
    if rc == FFI_OK then
        return ffi_str(cucharpp[0], sizep[0])
    end

    -- NGX_DECLINED: no extension
    if rc == -5 then
        return nil
    end

    return nil, ffi_str(errmsg[0])
end

-- tls.handshake.extension.type supported_version
local supported_versions_type = 43
local versions_map = {
    [0x002] = "SSLv2",
    [0x300] = "SSLv3",
    [0x301] = "TLSv1",
    [0x302] = "TLSv1.1",
    [0x303] = "TLSv1.2",
    [0x304] = "TLSv1.3",
}

-- return types, err
function _M.get_supported_versions()
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "ssl_client_hello" then
        error("API disabled in the current context")
    end

    local sizep = get_size_ptr()

    local rc = ngx_lua_ffi_ssl_get_client_hello_ext(r, supported_versions_type,
                                                    cucharpp, sizep, errmsg)

    if rc ~= FFI_OK then
        -- NGX_DECLINED: no extension
        if rc == -5 then
            return nil
        end

        return nil, ffi_str(errmsg[0])
    end

    local supported_versions_str = ffi_str(cucharpp[0], sizep[0])
    local remain_len = #supported_versions_str
    if remain_len == 0 then
        return nil
    end

    local supported_versions_len = byte(supported_versions_str, 1)
    remain_len = remain_len - 1

    if remain_len ~= supported_versions_len then
        return nil
    end
    local types = {}
    while remain_len >= 2  do
        local type_hi = byte(supported_versions_str, remain_len)
        local type_lo = byte(supported_versions_str, remain_len + 1)
        local type_id = lshift(type_hi, 8) + type_lo
        if versions_map[type_id] ~= nil then
            table_insert(types, versions_map[type_id])
        end
        remain_len = remain_len - 2
    end
    return types
end


local prot_map  = {
    ["SSLv2"] = 0x0002,
    ["SSLv3"] = 0x0004,
    ["TLSv1"] = 0x0008,
    ["TLSv1.1"] = 0x0010,
    ["TLSv1.2"] = 0x0020,
    ["TLSv1.3"] = 0x0040
}


-- return ok, err
function _M.set_protocols(protocols)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "ssl_client_hello" then
        error("API disabled in the current context")
    end

    local prots = 0
    for _, v in ipairs(protocols) do
        if not prot_map[v] then
            return nil, "invalid protocols failed"
        end
        prots = bor(prots, prot_map[v])
    end

    local rc = ngx_lua_ffi_ssl_set_protocols(r, prots, errmsg)
    if rc == FFI_OK then
        return true
    end

    return nil, ffi_str(errmsg[0])
end

return _M
