-- Copyright (C) Yichun Zhang. All rights reserved.


local base = require "resty.core.base"
base.allows_subsystem('http')
local core_response = require "resty.core.response"
local set_resp_header = core_response.set_resp_header


local _M = { version = base.version }


function _M.add_header(key, value)
    set_resp_header(nil, key, value, true)
end


return _M
