-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require 'ffi'
local ffi_new = ffi.new
local pcall = pcall
local error = error
local select = select
local ceil = math.ceil
local subsystem = ngx.config.subsystem


local str_buf_size = 4096
local str_buf
local size_ptr
local FREE_LIST_REF = 0


if subsystem == 'http' then
    if not ngx.config
       or not ngx.config.ngx_lua_version
       or ngx.config.ngx_lua_version ~= 10025
    then
        error("ngx_http_lua_module 0.10.25 required")
    end

elseif subsystem == 'stream' then
    if not ngx.config
       or not ngx.config.ngx_lua_version
       or ngx.config.ngx_lua_version ~= 13
    then
        error("ngx_stream_lua_module 0.0.13 required")
    end

else
    error("ngx_http_lua_module 0.10.25 or "
          .. "ngx_stream_lua_module 0.0.13 required")
end


if string.find(jit.version, " 2.0", 1, true) then
    ngx.log(ngx.ALERT, "use of lua-resty-core with LuaJIT 2.0 is ",
            "not recommended; use LuaJIT 2.1+ instead")
end


local ok, new_tab = pcall(require, "table.new")
if not ok then
    new_tab = function (narr, nrec) return {} end
end


local clear_tab
ok, clear_tab = pcall(require, "table.clear")
if not ok then
    local pairs = pairs
    clear_tab = function (tab)
                    for k, _ in pairs(tab) do
                        tab[k] = nil
                    end
                end
end


-- XXX for now LuaJIT 2.1 cannot compile require()
-- so we make the fast code path Lua only in our own
-- wrapper so that most of the require() calls in hot
-- Lua code paths can be JIT compiled.
do
    local orig_require = require
    local pkg_loaded = package.loaded
    -- the key_sentinel is inserted into package.loaded before
    -- the chunk is executed and replaced if the chunk completes normally.
    local key_sentinel = pkg_loaded[...]

    local function my_require(name)
        local mod = pkg_loaded[name]
        if mod then
            if mod == key_sentinel then
                error("loop or previous error loading module '" .. name .. "'")
            end

            return mod
        end
        return orig_require(name)
    end
    getfenv(0).require = my_require
end


if not pcall(ffi.typeof, "ngx_str_t") then
    ffi.cdef[[
        typedef struct {
            size_t                 len;
            const unsigned char   *data;
        } ngx_str_t;
    ]]
end


if subsystem == 'http' then
    if not pcall(ffi.typeof, "ngx_http_request_t") then
        ffi.cdef[[
            typedef struct ngx_http_request_s  ngx_http_request_t;
        ]]
    end

    if not pcall(ffi.typeof, "ngx_http_lua_ffi_str_t") then
        ffi.cdef[[
            typedef struct {
                int                       len;
                const unsigned char      *data;
            } ngx_http_lua_ffi_str_t;
        ]]
    end

elseif subsystem == 'stream' then
    if not pcall(ffi.typeof, "ngx_stream_lua_request_t") then
        ffi.cdef[[
            typedef struct ngx_stream_lua_request_s  ngx_stream_lua_request_t;
        ]]
    end

    if not pcall(ffi.typeof, "ngx_stream_lua_ffi_str_t") then
        ffi.cdef[[
            typedef struct {
                int                       len;
                const unsigned char      *data;
            } ngx_stream_lua_ffi_str_t;
        ]]
    end

else
    error("unknown subsystem: " .. subsystem)
end


local c_buf_type = ffi.typeof("char[?]")


local _M = new_tab(0, 18)


_M.version = "0.1.27"
_M.new_tab = new_tab
_M.clear_tab = clear_tab


local errmsg


function _M.get_errmsg_ptr()
    if not errmsg then
        errmsg = ffi_new("char *[1]")
    end
    return errmsg
end


if not ngx then
    error("no existing ngx. table found")
end


function _M.set_string_buf_size(size)
    if size <= 0 then
        return
    end
    if str_buf then
        str_buf = nil
    end
    str_buf_size = ceil(size)
end


function _M.get_string_buf_size()
    return str_buf_size
end


function _M.get_size_ptr()
    if not size_ptr then
        size_ptr = ffi_new("size_t[1]")
    end

    return size_ptr
end


function _M.get_string_buf(size, must_alloc)
    -- ngx.log(ngx.ERR, "str buf size: ", str_buf_size)
    if size > str_buf_size or must_alloc then
        local buf = ffi_new(c_buf_type, size)
        return buf
    end

    if not str_buf then
        str_buf = ffi_new(c_buf_type, str_buf_size)
    end

    return str_buf
end


function _M.ref_in_table(tb, key)
    if key == nil then
        return -1
    end
    local ref = tb[FREE_LIST_REF]
    if ref and ref ~= 0 then
         tb[FREE_LIST_REF] = tb[ref]

    else
        ref = #tb + 1
    end
    tb[ref] = key

    -- print("ref key_id returned ", ref)
    return ref
end


function _M.allows_subsystem(...)
    local total = select("#", ...)

    for i = 1, total do
        if select(i, ...) == subsystem then
            return
        end
    end

    error("unsupported subsystem: " .. subsystem, 2)
end


_M.FFI_OK = 0
_M.FFI_NO_REQ_CTX = -100
_M.FFI_BAD_CONTEXT = -101
_M.FFI_ERROR = -1
_M.FFI_AGAIN = -2
_M.FFI_BUSY = -3
_M.FFI_DONE = -4
_M.FFI_DECLINED = -5
_M.FFI_ABORT = -6


do
    local exdata

    ok, exdata = pcall(require, "thread.exdata")
    if ok and exdata then
        function _M.get_request()
            local r = exdata()
            if r ~= nil then
                return r
            end
        end

    else
        local getfenv = getfenv

        function _M.get_request()
            return getfenv(0).__ngx_req
        end
    end
end


return _M
