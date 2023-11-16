local base = require "resty.core.base"
local get_request = base.get_request

do
    local keys = {'create', 'yield', 'resume', 'status', 'wrap'}
    local errmsg = base.get_errmsg_ptr()
    local get_raw_phase = ngx.get_raw_phase

    for _, key in ipairs(keys) do
        local std = coroutine['_' .. key]
        local ours = coroutine['__' .. key]
        coroutine[key] = function (...)
            local r = get_request()
            if r ~= nil then
                local ctx = get_raw_phase(r, errmsg)
                if ctx ~= 0x020 and ctx ~= 0x040 then
                    return ours(...)
                end
            end
            return std(...)
        end
    end

    package.loaded.coroutine = coroutine
end

return {
    version = base.version
}
