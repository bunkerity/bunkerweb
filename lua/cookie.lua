local M         = {}
local session   = require "resty.session"

function M.is_set ()
        local s = session.open()
        if s and s.data.uri then
                return true
        end
        return false
end

function M.set ()
	local s = session.start()
	s.data.uri = ngx.var.request_uri
	s:save()
end

function M.get_uri ()
	return session.open().data.uri
end

return M
