local class     = require "bunkerweb.middleclass"
local logger    = require "bunkerweb.logger"
local settings  = require "bunkerweb.settings"
local plugin    = class("plugin")

function plugin:initialize(name, fill_settings)
    self.name = name
    self.logger = logger:new(name)
    self.settings = {}
    for i, setting in ipairs(fill_settings) do
        local value, err = settings:get(setting)
        if not value then
            local err = string.format("can't get setting %s : %s", setting, err)
            self.logger:log(ngx.ERR, err)
            return false, err
        end
        self.settings[setting] = value
    end
    return true, nil
end

return plugin