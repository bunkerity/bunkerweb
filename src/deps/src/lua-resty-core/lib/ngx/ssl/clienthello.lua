-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http', 'stream')


local ffi = require "ffi"
local bit  = require "bit"
local C = ffi.C
local ffi_str = ffi.string
local get_request = base.get_request
local error = error
local errmsg = base.get_errmsg_ptr()
local get_size_ptr = base.get_size_ptr
local FFI_OK = base.FFI_OK
local subsystem = ngx.config.subsystem
local ngx_phase = ngx.get_phase


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
        error("API disabled in the current context", 2)
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
        error("API disabled in the current context", 2)
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
        error("API disabled in the current context" .. ngx_phase(), 2)
    end

    local prots = 0
    for _, v in ipairs(protocols) do
        if not prot_map[v] then
            return nil, "invalid protocols failed"
        end
        prots = bit.bor(prots, prot_map[v])
    end

    local rc = ngx_lua_ffi_ssl_set_protocols(r, prots, errmsg)
    if rc == FFI_OK then
        return true
    end

    return nil, ffi_str(errmsg[0])
end

return _M
