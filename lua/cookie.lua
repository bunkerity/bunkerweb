
local M         = {}
local session   = require "resty.session"

local s = session.open()
if not s then
	s = session.start()
end

function M.is_set (key)
	if s.data[key] then
		return true
	end
	return false
end

function M.set (key, value)
	s.data[key] = value
end

function M.get (key)
	return s.data[key]
end

function M.save ()
	s:save()
end

return M
