-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require "ffi"
local debug = require "debug"
local base = require "resty.core.base"
local misc = require "resty.core.misc"


local C = ffi.C
local register_getter = misc.register_ngx_magic_key_getter
local register_setter = misc.register_ngx_magic_key_setter
local registry = debug.getregistry()
local new_tab = base.new_tab
local ref_in_table = base.ref_in_table
local get_request = base.get_request
local FFI_NO_REQ_CTX = base.FFI_NO_REQ_CTX
local FFI_OK = base.FFI_OK
local error = error
local setmetatable = setmetatable
local type = type
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_get_ctx_ref
local ngx_lua_ffi_set_ctx_ref


if subsystem == "http" then
    ffi.cdef[[
    int ngx_http_lua_ffi_get_ctx_ref(ngx_http_request_t *r, int *in_ssl_phase,
        int *ssl_ctx_ref);
    int ngx_http_lua_ffi_set_ctx_ref(ngx_http_request_t *r, int ref);
    ]]

    ngx_lua_ffi_get_ctx_ref = C.ngx_http_lua_ffi_get_ctx_ref
    ngx_lua_ffi_set_ctx_ref = C.ngx_http_lua_ffi_set_ctx_ref

elseif subsystem == "stream" then
    ffi.cdef[[
    int ngx_stream_lua_ffi_get_ctx_ref(ngx_stream_lua_request_t *r,
        int *in_ssl_phase, int *ssl_ctx_ref);
    int ngx_stream_lua_ffi_set_ctx_ref(ngx_stream_lua_request_t *r, int ref);
    ]]

    ngx_lua_ffi_get_ctx_ref = C.ngx_stream_lua_ffi_get_ctx_ref
    ngx_lua_ffi_set_ctx_ref = C.ngx_stream_lua_ffi_set_ctx_ref
end


local _M = {
    _VERSION = base.version
}


-- use a new ctxs table to make LuaJIT JIT compiler happy to generate more
-- efficient machine code.
local ctxs = {}
registry.ngx_lua_ctx_tables = ctxs


local get_ctx_table
do
    local in_ssl_phase = ffi.new("int[1]")
    local ssl_ctx_ref = ffi.new("int[1]")

    function get_ctx_table(ctx)
        local r = get_request()

        if not r then
            error("no request found")
        end

        local ctx_ref = ngx_lua_ffi_get_ctx_ref(r, in_ssl_phase, ssl_ctx_ref)
        if ctx_ref == FFI_NO_REQ_CTX then
            error("no request ctx found")
        end

        if ctx_ref < 0 then
            ctx_ref = ssl_ctx_ref[0]
            if ctx_ref > 0 and ctxs[ctx_ref] then
                if in_ssl_phase[0] ~= 0 then
                    return ctxs[ctx_ref]
                end

                if not ctx then
                    ctx = new_tab(0, 4)
                end

                ctx = setmetatable(ctx, ctxs[ctx_ref])

            else
                if in_ssl_phase[0] ~= 0 then
                    if not ctx then
                        ctx = new_tab(1, 4)
                    end

                    -- to avoid creating another table, we assume the users
                    -- won't overwrite the `__index` key
                    ctx.__index = ctx

                elseif not ctx then
                    ctx = new_tab(0, 4)
                end
            end

            ctx_ref = ref_in_table(ctxs, ctx)
            if ngx_lua_ffi_set_ctx_ref(r, ctx_ref) ~= FFI_OK then
                return nil
            end
            return ctx
        end
        return ctxs[ctx_ref]
    end
end
register_getter("ctx", get_ctx_table)
_M.get_ctx_table = get_ctx_table


local function set_ctx_table(ctx)
    local ctx_type = type(ctx)
    if ctx_type ~= "table" then
        error("ctx should be a table while getting a " .. ctx_type)
    end

    local r = get_request()

    if not r then
        error("no request found")
    end

    local ctx_ref = ngx_lua_ffi_get_ctx_ref(r, nil, nil)
    if ctx_ref == FFI_NO_REQ_CTX then
        error("no request ctx found")
    end

    if ctx_ref < 0 then
        ctx_ref = ref_in_table(ctxs, ctx)
        ngx_lua_ffi_set_ctx_ref(r, ctx_ref)
        return
    end
    ctxs[ctx_ref] = ctx
end
register_setter("ctx", set_ctx_table)


return _M
