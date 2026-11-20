-- LUA_INIT hook for all unit-test Lua processes; report mode uses LuaCov's line scanner.
local runner = require("luacov.runner")
local config = runner.load_config()
local directory = os.getenv("BW_LUA_COVERAGE_DIR")
if directory then
	-- Compiled LuaJIT traces bypass line hooks.
	local runtime = rawget(_G, "jit")
	if runtime then
		runtime.off()
	end
	-- Unique files prevent concurrent interpreters from overwriting each other's counts.
	local temporary = os.tmpname()
	os.remove(temporary)
	config.statsfile = directory .. "/" .. temporary:match("[^/]+$") .. ".stats.out"
	runner.init(config)
	return
end

assert(arg[1] == "report", "expected report mode or BW_LUA_COVERAGE_DIR")
local root, destination = arg[2], arg[3]
local stats = require("luacov.stats")
local combined = {}
for filename in io.lines() do
	combined[filename] = { max = 0, max_hits = 0 }
end
for i = 4, #arg do
	for filename, data in pairs(assert(stats.load(arg[i]))) do
		if filename:sub(1, 1) ~= "/" then
			filename = root .. "/" .. filename:gsub("^%./", "")
		end
		if combined[filename] then
			runner.update_stats(combined[filename], data)
		end
	end
end
config.statsfile = destination .. ".stats"
config.reportfile = destination
stats.save(config.statsfile, combined)

local base = require("luacov.reporter").ReporterBase
local reporter = setmetatable({}, { __index = base })
reporter.__index = reporter
function reporter:on_new_file(filename)
	self:write("SF:", filename:sub(#root + 2), "\n")
end
function reporter:on_hit_line(_, lineno, _, hits)
	self:write("DA:", lineno, ",", hits, "\n")
end
function reporter:on_mis_line(_, lineno)
	self:write("DA:", lineno, ",0\n")
end
function reporter:on_end_file(_, hits, misses)
	self:write("LF:", hits + misses, "\nLH:", hits, "\nend_of_record\n")
end
function reporter.on_file_error(_, filename, kind, message)
	error(kind .. " " .. filename .. ": " .. message)
end
local instance = assert(reporter:new(config))
instance:run()
instance:close()
