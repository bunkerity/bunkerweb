-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require 'ffi'
local base = require "resty.core.base"


local _M = {
    version = base.version
}

local ngx_shared = ngx.shared
if not ngx_shared then
    return _M
end


local ffi_new = ffi.new
local ffi_str = ffi.string
local C = ffi.C
local get_string_buf = base.get_string_buf
local get_string_buf_size = base.get_string_buf_size
local get_size_ptr = base.get_size_ptr
local tonumber = tonumber
local tostring = tostring
local next = next
local type = type
local error = error
local getmetatable = getmetatable
local FFI_DECLINED = base.FFI_DECLINED
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_shdict_get
local ngx_lua_ffi_shdict_incr
local ngx_lua_ffi_shdict_store
local ngx_lua_ffi_shdict_flush_all
local ngx_lua_ffi_shdict_get_ttl
local ngx_lua_ffi_shdict_set_expire
local ngx_lua_ffi_shdict_capacity
local ngx_lua_ffi_shdict_free_space
local ngx_lua_ffi_shdict_udata_to_zone


if subsystem == 'http' then
    ffi.cdef[[
int ngx_http_lua_ffi_shdict_get(void *zone, const unsigned char *key,
    size_t key_len, int *value_type, unsigned char **str_value_buf,
    size_t *str_value_len, double *num_value, int *user_flags,
    int get_stale, int *is_stale, char **errmsg);

int ngx_http_lua_ffi_shdict_incr(void *zone, const unsigned char *key,
    size_t key_len, double *value, char **err, int has_init,
    double init, long init_ttl, int *forcible);

int ngx_http_lua_ffi_shdict_store(void *zone, int op,
    const unsigned char *key, size_t key_len, int value_type,
    const unsigned char *str_value_buf, size_t str_value_len,
    double num_value, long exptime, int user_flags, char **errmsg,
    int *forcible);

int ngx_http_lua_ffi_shdict_flush_all(void *zone);

long ngx_http_lua_ffi_shdict_get_ttl(void *zone,
    const unsigned char *key, size_t key_len);

int ngx_http_lua_ffi_shdict_set_expire(void *zone,
    const unsigned char *key, size_t key_len, long exptime);

size_t ngx_http_lua_ffi_shdict_capacity(void *zone);

void *ngx_http_lua_ffi_shdict_udata_to_zone(void *zone_udata);
    ]]

    ngx_lua_ffi_shdict_get = C.ngx_http_lua_ffi_shdict_get
    ngx_lua_ffi_shdict_incr = C.ngx_http_lua_ffi_shdict_incr
    ngx_lua_ffi_shdict_store = C.ngx_http_lua_ffi_shdict_store
    ngx_lua_ffi_shdict_flush_all = C.ngx_http_lua_ffi_shdict_flush_all
    ngx_lua_ffi_shdict_get_ttl = C.ngx_http_lua_ffi_shdict_get_ttl
    ngx_lua_ffi_shdict_set_expire = C.ngx_http_lua_ffi_shdict_set_expire
    ngx_lua_ffi_shdict_capacity = C.ngx_http_lua_ffi_shdict_capacity
    ngx_lua_ffi_shdict_udata_to_zone =
        C.ngx_http_lua_ffi_shdict_udata_to_zone

    if not pcall(function ()
        return C.ngx_http_lua_ffi_shdict_free_space
    end)
    then
        ffi.cdef[[
size_t ngx_http_lua_ffi_shdict_free_space(void *zone);
        ]]
    end

    pcall(function ()
        ngx_lua_ffi_shdict_free_space = C.ngx_http_lua_ffi_shdict_free_space
    end)

elseif subsystem == 'stream' then

    ffi.cdef[[
int ngx_stream_lua_ffi_shdict_get(void *zone, const unsigned char *key,
    size_t key_len, int *value_type, unsigned char **str_value_buf,
    size_t *str_value_len, double *num_value, int *user_flags,
    int get_stale, int *is_stale, char **errmsg);

int ngx_stream_lua_ffi_shdict_incr(void *zone, const unsigned char *key,
    size_t key_len, double *value, char **err, int has_init,
    double init, long init_ttl, int *forcible);

int ngx_stream_lua_ffi_shdict_store(void *zone, int op,
    const unsigned char *key, size_t key_len, int value_type,
    const unsigned char *str_value_buf, size_t str_value_len,
    double num_value, long exptime, int user_flags, char **errmsg,
    int *forcible);

int ngx_stream_lua_ffi_shdict_flush_all(void *zone);

long ngx_stream_lua_ffi_shdict_get_ttl(void *zone,
     const unsigned char *key, size_t key_len);

int ngx_stream_lua_ffi_shdict_set_expire(void *zone,
    const unsigned char *key, size_t key_len, long exptime);

size_t ngx_stream_lua_ffi_shdict_capacity(void *zone);

void *ngx_stream_lua_ffi_shdict_udata_to_zone(void *zone_udata);
    ]]

    ngx_lua_ffi_shdict_get = C.ngx_stream_lua_ffi_shdict_get
    ngx_lua_ffi_shdict_incr = C.ngx_stream_lua_ffi_shdict_incr
    ngx_lua_ffi_shdict_store = C.ngx_stream_lua_ffi_shdict_store
    ngx_lua_ffi_shdict_flush_all = C.ngx_stream_lua_ffi_shdict_flush_all
    ngx_lua_ffi_shdict_get_ttl = C.ngx_stream_lua_ffi_shdict_get_ttl
    ngx_lua_ffi_shdict_set_expire = C.ngx_stream_lua_ffi_shdict_set_expire
    ngx_lua_ffi_shdict_capacity = C.ngx_stream_lua_ffi_shdict_capacity
    ngx_lua_ffi_shdict_udata_to_zone =
        C.ngx_stream_lua_ffi_shdict_udata_to_zone

    if not pcall(function ()
        return C.ngx_stream_lua_ffi_shdict_free_space
    end)
    then
        ffi.cdef[[
size_t ngx_stream_lua_ffi_shdict_free_space(void *zone);
        ]]
    end

    -- ngx_stream_lua is only compatible with NGINX >= 1.13.6, meaning it
    -- cannot lack support for ngx_stream_lua_ffi_shdict_free_space.
    ngx_lua_ffi_shdict_free_space = C.ngx_stream_lua_ffi_shdict_free_space

else
    error("unknown subsystem: " .. subsystem)
end

if not pcall(function () return C.free end) then
    ffi.cdef[[
void free(void *ptr);
    ]]
end


local value_type = ffi_new("int[1]")
local user_flags = ffi_new("int[1]")
local num_value = ffi_new("double[1]")
local is_stale = ffi_new("int[1]")
local forcible = ffi_new("int[1]")
local str_value_buf = ffi_new("unsigned char *[1]")
local errmsg = base.get_errmsg_ptr()


local function check_zone(zone)
    if not zone or type(zone) ~= "table" then
        error("bad \"zone\" argument", 3)
    end

    zone = zone[1]
    if type(zone) ~= "userdata" then
        error("bad \"zone\" argument", 3)
    end

    zone = ngx_lua_ffi_shdict_udata_to_zone(zone)
    if zone == nil then
        error("bad \"zone\" argument", 3)
    end

    return zone
end


local function shdict_store(zone, op, key, value, exptime, flags)
    zone = check_zone(zone)

    if not exptime then
        exptime = 0
    elseif exptime < 0 then
        error('bad "exptime" argument', 2)
    end

    if not flags then
        flags = 0
    end

    if key == nil then
        return nil, "nil key"
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key
    if key_len == 0 then
        return nil, "empty key"
    end
    if key_len > 65535 then
        return nil, "key too long"
    end

    local str_val_buf
    local str_val_len = 0
    local num_val = 0
    local valtyp = type(value)

    -- print("value type: ", valtyp)
    -- print("exptime: ", exptime)

    if valtyp == "string" then
        valtyp = 4  -- LUA_TSTRING
        str_val_buf = value
        str_val_len = #value

    elseif valtyp == "number" then
        valtyp = 3  -- LUA_TNUMBER
        num_val = value

    elseif value == nil then
        valtyp = 0  -- LUA_TNIL

    elseif valtyp == "boolean" then
        valtyp = 1  -- LUA_TBOOLEAN
        num_val = value and 1 or 0

    else
        return nil, "bad value type"
    end

    local rc = ngx_lua_ffi_shdict_store(zone, op, key, key_len,
                                        valtyp, str_val_buf,
                                        str_val_len, num_val,
                                        exptime * 1000, flags, errmsg,
                                        forcible)

    -- print("rc == ", rc)

    if rc == 0 then  -- NGX_OK
        return true, nil, forcible[0] == 1
    end

    -- NGX_DECLINED or NGX_ERROR
    return false, ffi_str(errmsg[0]), forcible[0] == 1
end


local function shdict_set(zone, key, value, exptime, flags)
    return shdict_store(zone, 0, key, value, exptime, flags)
end


local function shdict_safe_set(zone, key, value, exptime, flags)
    return shdict_store(zone, 0x0004, key, value, exptime, flags)
end


local function shdict_add(zone, key, value, exptime, flags)
    return shdict_store(zone, 0x0001, key, value, exptime, flags)
end


local function shdict_safe_add(zone, key, value, exptime, flags)
    return shdict_store(zone, 0x0005, key, value, exptime, flags)
end


local function shdict_replace(zone, key, value, exptime, flags)
    return shdict_store(zone, 0x0002, key, value, exptime, flags)
end


local function shdict_delete(zone, key)
    return shdict_set(zone, key, nil)
end


local function shdict_get(zone, key)
    zone = check_zone(zone)

    if key == nil then
        return nil, "nil key"
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key
    if key_len == 0 then
        return nil, "empty key"
    end
    if key_len > 65535 then
        return nil, "key too long"
    end

    local size = get_string_buf_size()
    local buf = get_string_buf(size)
    str_value_buf[0] = buf
    local value_len = get_size_ptr()
    value_len[0] = size

    local rc = ngx_lua_ffi_shdict_get(zone, key, key_len, value_type,
                                      str_value_buf, value_len,
                                      num_value, user_flags, 0,
                                      is_stale, errmsg)
    if rc ~= 0 then
        if errmsg[0] ~= nil then
            return nil, ffi_str(errmsg[0])
        end

        error("failed to get the key")
    end

    local typ = value_type[0]

    if typ == 0 then -- LUA_TNIL
        return nil
    end

    local flags = tonumber(user_flags[0])

    local val

    if typ == 4 then -- LUA_TSTRING
        if str_value_buf[0] ~= buf then
            -- ngx.say("len: ", tonumber(value_len[0]))
            buf = str_value_buf[0]
            val = ffi_str(buf, value_len[0])
            C.free(buf)
        else
            val = ffi_str(buf, value_len[0])
        end

    elseif typ == 3 then -- LUA_TNUMBER
        val = tonumber(num_value[0])

    elseif typ == 1 then -- LUA_TBOOLEAN
        val = (tonumber(buf[0]) ~= 0)

    else
        error("unknown value type: " .. typ)
    end

    if flags ~= 0 then
        return val, flags
    end

    return val
end


local function shdict_get_stale(zone, key)
    zone = check_zone(zone)

    if key == nil then
        return nil, "nil key"
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key
    if key_len == 0 then
        return nil, "empty key"
    end
    if key_len > 65535 then
        return nil, "key too long"
    end

    local size = get_string_buf_size()
    local buf = get_string_buf(size)
    str_value_buf[0] = buf
    local value_len = get_size_ptr()
    value_len[0] = size

    local rc = ngx_lua_ffi_shdict_get(zone, key, key_len, value_type,
                                      str_value_buf, value_len,
                                      num_value, user_flags, 1,
                                      is_stale, errmsg)
    if rc ~= 0 then
        if errmsg[0] ~= nil then
            return nil, ffi_str(errmsg[0])
        end

        error("failed to get the key")
    end

    local typ = value_type[0]

    if typ == 0 then -- LUA_TNIL
        return nil
    end

    local flags = tonumber(user_flags[0])
    local val

    if typ == 4 then -- LUA_TSTRING
        if str_value_buf[0] ~= buf then
            -- ngx.say("len: ", tonumber(value_len[0]))
            buf = str_value_buf[0]
            val = ffi_str(buf, value_len[0])
            C.free(buf)
        else
            val = ffi_str(buf, value_len[0])
        end

    elseif typ == 3 then -- LUA_TNUMBER
        val = tonumber(num_value[0])

    elseif typ == 1 then -- LUA_TBOOLEAN
        val = (tonumber(buf[0]) ~= 0)

    else
        error("unknown value type: " .. typ)
    end

    if flags ~= 0 then
        return val, flags, is_stale[0] == 1
    end

    return val, nil, is_stale[0] == 1
end


local function shdict_incr(zone, key, value, init, init_ttl)
    zone = check_zone(zone)

    if key == nil then
        return nil, "nil key"
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key
    if key_len == 0 then
        return nil, "empty key"
    end
    if key_len > 65535 then
        return nil, "key too long"
    end

    if type(value) ~= "number" then
        value = tonumber(value)
    end
    num_value[0] = value

    if init then
        local typ = type(init)
        if typ ~= "number" then
            init = tonumber(init)

            if not init then
                error("bad init arg: number expected, got " .. typ, 2)
            end
        end
    end

    if init_ttl ~= nil then
        local typ = type(init_ttl)
        if typ ~= "number" then
            init_ttl = tonumber(init_ttl)

            if not init_ttl then
                error("bad init_ttl arg: number expected, got " .. typ, 2)
            end
        end

        if init_ttl < 0 then
            error('bad "init_ttl" argument', 2)
        end

        if not init then
            error('must provide "init" when providing "init_ttl"', 2)
        end

    else
        init_ttl = 0
    end

    local rc = ngx_lua_ffi_shdict_incr(zone, key, key_len, num_value,
                                       errmsg, init and 1 or 0,
                                       init or 0, init_ttl * 1000,
                                       forcible)
    if rc ~= 0 then  -- ~= NGX_OK
        return nil, ffi_str(errmsg[0])
    end

    if not init then
        return tonumber(num_value[0])
    end

    return tonumber(num_value[0]), nil, forcible[0] == 1
end


local function shdict_flush_all(zone)
    zone = check_zone(zone)

    ngx_lua_ffi_shdict_flush_all(zone)
end


local function shdict_ttl(zone, key)
    zone = check_zone(zone)

    if key == nil then
        return nil, "nil key"
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key
    if key_len == 0 then
        return nil, "empty key"
    end

    if key_len > 65535 then
        return nil, "key too long"
    end

    local rc = ngx_lua_ffi_shdict_get_ttl(zone, key, key_len)

    if rc == FFI_DECLINED then
        return nil, "not found"
    end

    return tonumber(rc) / 1000
end


local function shdict_expire(zone, key, exptime)
    zone = check_zone(zone)

    if not exptime then
        error('bad "exptime" argument', 2)
    end

    if key == nil then
        return nil, "nil key"
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key
    if key_len == 0 then
        return nil, "empty key"
    end

    if key_len > 65535 then
        return nil, "key too long"
    end

    local rc = ngx_lua_ffi_shdict_set_expire(zone, key, key_len,
                                             exptime * 1000)

    if rc == FFI_DECLINED then
        return nil, "not found"
    end

    -- NGINX_OK/FFI_OK

    return true
end


local function shdict_capacity(zone)
    zone = check_zone(zone)

    return tonumber(ngx_lua_ffi_shdict_capacity(zone))
end


local shdict_free_space
if ngx_lua_ffi_shdict_free_space then
    shdict_free_space = function (zone)
        zone = check_zone(zone)

        return tonumber(ngx_lua_ffi_shdict_free_space(zone))
    end

else
    shdict_free_space = function ()
        error("'shm:free_space()' not supported in NGINX < 1.11.7", 2)
    end
end


local _, dict = next(ngx_shared, nil)
if dict then
    local mt = getmetatable(dict)
    if mt then
        mt = mt.__index
        if mt then
            mt.get = shdict_get
            mt.get_stale = shdict_get_stale
            mt.incr = shdict_incr
            mt.set = shdict_set
            mt.safe_set = shdict_safe_set
            mt.add = shdict_add
            mt.safe_add = shdict_safe_add
            mt.replace = shdict_replace
            mt.delete = shdict_delete
            mt.flush_all = shdict_flush_all
            mt.ttl = shdict_ttl
            mt.expire = shdict_expire
            mt.capacity = shdict_capacity
            mt.free_space = shdict_free_space
        end
    end
end


return _M
