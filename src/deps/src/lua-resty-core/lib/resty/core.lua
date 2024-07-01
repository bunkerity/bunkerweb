-- Copyright (C) Yichun Zhang (agentzh)

local subsystem = ngx.config.subsystem


require "resty.core.var"
require "resty.core.worker"
require "resty.core.regex"
require "resty.core.shdict"
require "resty.core.time"
require "resty.core.hash"
require "resty.core.uri"
require "resty.core.exit"
require "resty.core.base64"
require "resty.core.request"


if subsystem == 'http' then
    require "resty.core.response"
    require "resty.core.phase"
    require "resty.core.ndk"
    require "resty.core.socket"
    require "resty.core.coroutine"
    require "resty.core.param"
end


require "resty.core.misc"
require "resty.core.ctx"


local base = require "resty.core.base"


return {
    version = base.version
}
