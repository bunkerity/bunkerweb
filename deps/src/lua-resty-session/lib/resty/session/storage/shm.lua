local lock         = require "resty.lock"

local setmetatable = setmetatable
local tonumber     = tonumber
local concat       = table.concat
local var          = ngx.var
local shared       = ngx.shared

local function enabled(value)
    if value == nil then return nil end
    return value == true or (value == "1" or value == "true" or value == "on")
end

local function ifnil(value, default)
    if value == nil then
        return default
    end

    return enabled(value)
end

local defaults   = {
    store        = var.session_shm_store                       or "sessions",
    uselocking   = enabled(var.session_shm_uselocking          or true),
    lock         = {
        exptime  = tonumber(var.session_shm_lock_exptime,  10) or 30,
        timeout  = tonumber(var.session_shm_lock_timeout,  10) or 5,
        step     = tonumber(var.session_shm_lock_step,     10) or 0.001,
        ratio    = tonumber(var.session_shm_lock_ratio,    10) or 2,
        max_step = tonumber(var.session_shm_lock_max_step, 10) or 0.5,
    }
}

local storage = {}

storage.__index = storage

function storage.new(session)
    local config = session.shm            or defaults
    local store  = config.store           or defaults.store
    local locking = ifnil(config.uselocking, defaults.uselocking)

    local self = {
        store      = shared[store],
        uselocking = locking,
    }

    if locking then
        local lock_opts = config.lock                      or defaults.lock
        local opts      = {
            exptime     = tonumber(lock_opts.exptime,  10) or defaults.exptime,
            timeout     = tonumber(lock_opts.timeout,  10) or defaults.timeout,
            step        = tonumber(lock_opts.step,     10) or defaults.step,
            ratio       = tonumber(lock_opts.ratio,    10) or defaults.ratio,
            max_step    = tonumber(lock_opts.max_step, 10) or defaults.max_step,
        }
        self.lock = lock:new(store, opts)
    end

    return setmetatable(self, storage)
end

function storage:open(id, keep_lock)
    if self.uselocking then
        local ok, err = self.lock:lock(concat{ id, ".lock" })
        if not ok then
            return nil, err
        end
    end

    local data, err = self.store:get(id)

    if self.uselocking and (err or not data or not keep_lock) then
        self.lock:unlock()
    end

    return data, err
end

function storage:start(id)
    if self.uselocking then
        return self.lock:lock(concat{ id, ".lock" })
    end

    return true
end

function storage:save(id, ttl, data, close)
    local ok, err = self.store:set(id, data, ttl)
    if close and self.uselocking then
        self.lock:unlock()
    end

    return ok, err
end

function storage:close()
    if self.uselocking then
        self.lock:unlock()
    end

    return true
end

function storage:destroy(id)
    self.store:delete(id)

    if self.uselocking then
        self.lock:unlock()
    end

    return true
end

function storage:ttl(id, lifetime, close)
    local ok, err = self.store:expire(id, lifetime)

    if close and self.uselocking then
        self.lock:unlock()
    end

    return ok, err
end

return storage
