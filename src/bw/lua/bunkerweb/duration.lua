local match = string.match
local floor = math.floor
local tonumber = tonumber

local units = {
	ms = 1,
	s = 1000,
	m = 60000,
	h = 3600000,
	d = 86400000,
	w = 604800000,
	M = 2592000000,
	y = 31536000000,
}

local duration = {}

function duration.parse_duration(value, default_unit)
	if value == nil or value == "" then
		return nil
	end
	local amount, suffix = match(value, "^(%d+)(%a*)$")
	local default_factor = units[default_unit]
	local factor = units[suffix == "" and default_unit or suffix]
	if not amount or not default_factor or not factor then
		return nil
	end
	amount = tonumber(amount)
	local result = floor(amount * factor / default_factor)
	-- 0 means permanent or disabled to the callers: a non-zero duration below the unit must not become it
	if result == 0 and amount > 0 then
		return 1
	end
	return result
end

return duration
