
local M         = {}
local session   = require "resty.session"

function M.session ()
	local s = session:open()
	if not s.started then
		s:start()
	end
	return s
end

function M.is_set (key)
	local s = M.session()
	if s.data[key] then
		return true
	end
	return false
end

function M.set (values)
	local s = M.session()
	for k, v in pairs(values) do
		s.data[k] = v
	end
	s:save()
end

function M.get (key)
	local s = M.session ()
	return s.data[key]
end

return M
