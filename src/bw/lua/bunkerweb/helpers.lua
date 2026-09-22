local ngx = ngx
local base = require "resty.core.base"
local bwctx = require "bunkerweb.ctx"
local cjson = require "cjson"
local utils = require "bunkerweb.utils"

local open = io.open
local decode = cjson.decode
local encode = cjson.encode
local tostring = tostring
local get_phases = utils.get_phases
local get_request = base.get_request
local apply_ref = bwctx.apply_ref
local stash_ref = bwctx.stash_ref
local subsystem = ngx.config.subsystem
local var = ngx.var
local req = ngx.req
local shared = ngx.shared
local ip_is_global = utils.ip_is_global
local is_ipv4 = utils.is_ipv4
local is_ipv6 = utils.is_ipv6
local get_variable = utils.get_variable
local get_country = utils.get_country
local get_asn = utils.get_asn
local get_city = utils.get_city
local rand = utils.rand
local lower = string.lower
local upper = string.upper
local now = ngx.now
local update_time = ngx.update_time

local helpers = {}

-- Geo lookups are reported once per worker : a missing MMDB would otherwise log on every request
local geo_country_warned = false
local geo_asn_warned = false
local export_vars_warned = false
local geo_city_warned = false

-- Resolved once per worker. METRICS_COLLECT_TIMINGS is a global setting and a settings
-- change goes through a reload (which restarts workers), so a per-worker memo is correct
-- and keeps call_plugin from hitting the datastore on every plugin call.
local collect_timings = nil

helpers.load_plugin = function(json)
	-- Open file
	local file, err, nb = open(json, "r")
	if not file then
		return false, "can't load JSON at " .. json .. " : " .. err .. " (nb = " .. tostring(nb) .. ")"
	end
	-- Decode JSON
	local ok, plugin = pcall(decode, file:read("*a"))
	file:close()
	if not ok then
		-- `plugin` holds pcall's error message here, not `err` (that's the earlier io.open result,
		-- already nil on this path) -- concatenating `err` crashed on every malformed JSON file.
		return false, "invalid JSON at " .. json .. " : " .. tostring(plugin)
	end
	if type(plugin) ~= "table" then
		-- A scalar/boolean top-level JSON value (`123`, `true`, ...) decodes fine but isn't
		-- indexable the way every check below assumes.
		return false, "manifest at " .. json .. " is not an object"
	end
	-- Check fields
	local missing_fields = {}
	local required_fields = { "id", "name", "description", "version", "settings", "stream" }
	for _, field in ipairs(required_fields) do
		if plugin[field] == nil then
			table.insert(missing_fields, field)
		end
	end
	if #missing_fields > 0 then
		return false, "missing field(s) " .. encode(missing_fields) .. " for JSON at " .. json
	end
	-- Manifest caps, mirrored by hand from Configurator.__validate_plugin / MANIFEST_CAPS
	-- (src/common/gen/Configurator.py) : a plugin.json Python refuses must be refused here too,
	-- with the same field named, or the "loads in Lua while dropped from the generated
	-- configuration" split-brain (PX-A §2.2) comes right back. `extensions` stays Python-only
	-- (never read here) and jobs are not re-validated (Python already owns job dispatch). Lengths
	-- are bytes (Lua `#`), matching Python's `len(value.encode())` -- see MANIFEST_CAPS. Every
	-- field is type-checked before it is indexed or measured : this runs inside
	-- `init_by_lua_block`, so an uncaught Lua error here is fatal to NGINX startup, not a single
	-- dropped plugin the way an unexpected type is on the Python side.
	local at_json = " for JSON at " .. json
	if type(plugin.id) ~= "string" then
		return false, "id of plugin " .. tostring(plugin.id) .. " must be a string" .. at_json
	end
	if not plugin.id:match("^[%w_.-]+$") or #plugin.id > 64 then
		return false, "id of plugin " .. plugin.id .. " is invalid, must match ^[\\w.-]{1,64}$" .. at_json
	end
	if type(plugin.name) ~= "string" then
		return false, "name of plugin " .. plugin.id .. " must be a string" .. at_json
	end
	if #plugin.name > 128 then
		return false, "name of plugin " .. plugin.id .. " is " .. #plugin.name .. " bytes, max 128" .. at_json
	end
	if type(plugin.description) ~= "string" then
		return false, "description of plugin " .. plugin.id .. " must be a string" .. at_json
	end
	if #plugin.description > 256 then
		return false,
			"description of plugin " .. plugin.id .. " is " .. #plugin.description .. " bytes, max 256" .. at_json
	end
	if type(plugin.version) ~= "string" then
		return false, "version of plugin " .. plugin.id .. " must be a string" .. at_json
	end
	if not (plugin.version:match("^%d+%.%d+%.%d+$") or plugin.version:match("^%d+%.%d+$")) then
		return false,
			"version of plugin "
				.. plugin.id
				.. " is "
				.. plugin.version
				.. ", must match ^\\d+\\.\\d+(\\.\\d+)?$"
				.. at_json
	end
	if plugin.stream ~= "yes" and plugin.stream ~= "no" and plugin.stream ~= "partial" then
		return false,
			"stream of plugin "
				.. plugin.id
				.. " is "
				.. tostring(plugin.stream)
				.. ", must be one of no, partial, yes"
				.. at_json
	end
	if type(plugin.settings) ~= "table" then
		return false, "settings of plugin " .. plugin.id .. " must be an object" .. at_json
	end
	local setting_mandatory_keys = { "context", "default", "help", "id", "label", "regex", "type" }
	local valid_setting_types = {
		password = true,
		text = true,
		number = true,
		file = true,
		check = true,
		select = true,
		multiselect = true,
		multivalue = true,
		size = true,
		duration = true,
	}
	-- Sorted, not raw `pairs()` order (undefined in Lua, hash-seeded per process) : with several
	-- defects in one manifest the field named in the refusal must be reproducible across restarts.
	-- It does NOT make the named field match Python's (which walks the JSON's own insertion
	-- order) when more than one setting is broken -- only the VERDICT (refuse) is guaranteed to
	-- agree, which is what the brief asks for. This pass also catches a `settings` that decoded as
	-- a JSON array (integer keys, not setting ids) before it can reach the string-only checks
	-- below.
	local setting_names = {}
	for setting_key in pairs(plugin.settings) do
		if type(setting_key) ~= "string" then
			return false, "settings of plugin " .. plugin.id .. " must be an object keyed by setting id" .. at_json
		end
		table.insert(setting_names, setting_key)
	end
	table.sort(setting_names)
	for _, setting in ipairs(setting_names) do
		local data = plugin.settings[setting]
		if type(data) ~= "table" then
			return false, "setting " .. setting .. " of plugin " .. plugin.id .. " must be an object" .. at_json
		end
		local missing_setting_keys = {}
		for _, key in ipairs(setting_mandatory_keys) do
			if data[key] == nil then
				table.insert(missing_setting_keys, key)
			end
		end
		if #missing_setting_keys > 0 then
			table.sort(missing_setting_keys)
			return false,
				"setting " .. setting .. " of plugin " .. plugin.id .. " is missing key(s) " .. table.concat(
					missing_setting_keys,
					", "
				) .. ", must have context, default, help, id, label, regex, type" .. at_json
		end
		if not setting:match("^[A-Z0-9_]+$") or #setting > 256 then
			return false,
				"id of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is invalid, must match ^[A-Z0-9_]{1,256}$"
					.. at_json
		end
		if data.context ~= "global" and data.context ~= "multisite" then
			return false,
				"context of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is "
					.. tostring(data.context)
					.. ", must be one of global, multisite"
					.. at_json
		end
		if type(data.default) ~= "string" then
			return false,
				"default of setting " .. setting .. " of plugin " .. plugin.id .. " must be a string" .. at_json
		end
		if #data.default > 4096 then
			return false,
				"default of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is "
					.. #data.default
					.. " bytes, max 4096"
					.. at_json
		end
		if type(data.help) ~= "string" then
			return false, "help of setting " .. setting .. " of plugin " .. plugin.id .. " must be a string" .. at_json
		end
		if #data.help > 512 then
			return false,
				"help of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is "
					.. #data.help
					.. " bytes, max 512"
					.. at_json
		end
		if type(data.label) ~= "string" then
			return false, "label of setting " .. setting .. " of plugin " .. plugin.id .. " must be a string" .. at_json
		end
		if #data.label > 256 then
			return false,
				"label of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is "
					.. #data.label
					.. " bytes, max 256"
					.. at_json
		end
		if type(data.regex) ~= "string" then
			return false, "regex of setting " .. setting .. " of plugin " .. plugin.id .. " must be a string" .. at_json
		end
		if #data.regex > 1024 then
			return false,
				"regex of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is "
					.. #data.regex
					.. " bytes, max 1024"
					.. at_json
		end
		if not valid_setting_types[data.type] then
			return false,
				"type of setting "
					.. setting
					.. " of plugin "
					.. plugin.id
					.. " is "
					.. tostring(data.type)
					.. ", must be one of check, duration, file, multiselect, multivalue, number, password, select, size, text"
					.. at_json
		end
	end
	-- Try require
	local plugin_lua, err = helpers.require_plugin(plugin.id)
	if plugin_lua == false then
		return false, err
	end
	-- Fill phases
	local phases = get_phases()
	plugin.phases = {}
	if plugin_lua then
		for _, phase in ipairs(phases) do
			if plugin_lua[phase] ~= nil then
				table.insert(plugin.phases, phase)
			end
		end
	end
	-- Return plugin
	return true, plugin
end

local function parse_override(value)
	if type(value) ~= "string" or value == "" then
		return {}
	end

	local ids = {}
	for token in value:gmatch("%S+") do
		table.insert(ids, token)
	end

	return ids
end

-- Origin buckets for the per-phase default list. A plugin's `type` is set at load time from the
-- root its plugin.json was found under (init-lua.conf / init-stream-lua.conf), never from the
-- manifest, so an external plugin cannot declare itself PRO to jump the queue. Anything without
-- a known origin sorts with core, which is the conservative end of the list.
local ORIGIN_RANK = { pro = 1, external = 2, core = 3 }

-- How many unknown ids of one (plugin, phase) get a line of their own before the rest are
-- summarised. The list a manifest may declare is unbounded, error.log is not.
local MAX_UNKNOWN_ORDER_WARNINGS = 5

-- cjson decodes a JSON array and a JSON object into the same Lua table type, so "is this a list?"
-- is "are its keys exactly 1..#t?". An empty object and an empty array stay indistinguishable --
-- the one shape the two validators cannot be made to agree on, and a harmless one: both halves
-- read it as "no constraint".
local function is_list(value)
	if type(value) ~= "table" then
		return false
	end
	local count = 0
	for key in pairs(value) do
		if type(key) ~= "number" then
			return false
		end
		count = count + 1
	end
	return count == #value
end

-- Only the literal "*" is the wildcard; anything else must be a plugin id -- same shape and same
-- 64-byte cap as helpers.load_plugin and Configurator.__plugin_id_rx (compiled with re.ASCII, so
-- its \w is ASCII-only and Lua's %w agrees).
local function is_order_entry(id)
	-- Length first, pattern second : the pattern is O(n) and n is attacker-controlled, while the
	-- cap is the check that refuses it anyway. Same verdict, O(1) on a hostile entry.
	return type(id) == "string" and (id == "*" or (#id <= 64 and id:match("^[%w_.-]+$") ~= nil))
end

-- Every manifest-supplied value these refusals quote -- the offending entry, the phase name, an
-- unknown constraint key -- is unbounded : the 64-byte cap is precisely the check the refused one
-- failed. Each refusal is one error.log line per configuration load, so quoting one whole is the
-- same flood MAX_UNKNOWN_ORDER_WARNINGS closes, reached through a single value.
-- The cut is on bytes, so a multibyte value can leave a partial UTF-8 sequence in the log : that
-- is cosmetic, and LuaJIT has no utf8 library to do better cheaply.
-- Configurator.__validate_plugin_order bounds the same three values the same way.
local function shown_order_value(value)
	local text = tostring(value)
	local truncated = #text > 64
	if truncated then
		-- Cut before escaping : the value can be megabytes long and the tail is dropped anyway.
		text = text:sub(1, 64)
	end
	-- Control bytes are replaced, not merely truncated : logger:log hands the message to
	-- ngx_log_error as "%*s", which copies it verbatim, so a newline in a manifest value would
	-- forge a second, genuine-looking error.log line.
	text = text:gsub("%c", "?")
	if truncated then
		return text .. "... (truncated)"
	end
	return text
end

-- Normalise a plugin.json "order" block into { [phase] = { before = {...}, after = {...} } }.
-- Returns the map, or nil plus a message. Any defect refuses the WHOLE declaration, exactly like
-- Configurator.__validate_plugin_order, whose caller returns on the first one and pops the `order`
-- key. Anything looser and that caller's "ignoring the order declaration" log line is a lie: the
-- Lua runtime re-reads plugin.json from disk and never sees the pop, so a plugin could reorder a
-- phase while the operator's log said the declaration had been ignored (SEC F-09). A refusal is
-- never fatal to the plugin -- the declaration is dropped and the default order stands, which is
-- why the Python half warns instead of refusing too.
local function parse_declared_order(plugin_id, order, phases_set, phase_aliases)
	if type(order) ~= "table" then
		return nil, "Invalid order for plugin " .. plugin_id .. " (Must be an object)"
	end
	-- Sorted, not raw `pairs()` order (hash-seeded per process) : with two defects in one block
	-- the message must name the same one across restarts. It does NOT make that one match
	-- Python's (which walks the JSON's own insertion order) -- only the verdict is guaranteed to
	-- agree, which is what the split-brain needs.
	local phase_names = {}
	for phase in pairs(order) do
		if type(phase) ~= "string" then
			-- A JSON array, or any non-object : Python's isinstance(order, dict) refuses it.
			return nil, "Invalid order for plugin " .. plugin_id .. " (Must be an object)"
		end
		table.insert(phase_names, phase)
	end
	table.sort(phase_names)

	local declared = {}
	for _, phase in ipairs(phase_names) do
		local constraints = order[phase]
		local canonical_phase = phase_aliases[phase] or phase
		if not phases_set[canonical_phase] then
			return nil,
				"Invalid order phase "
					.. shown_order_value(phase)
					.. " for plugin "
					.. plugin_id
					.. " (Must be one of the plugin phases)"
		end
		if type(constraints) ~= "table" then
			return nil,
				"Invalid order for phase "
					.. shown_order_value(phase)
					.. " in plugin "
					.. plugin_id
					.. " (Must be an object with before and/or after)"
		end
		local unknown_keys = {}
		for key in pairs(constraints) do
			if key ~= "before" and key ~= "after" then
				table.insert(unknown_keys, shown_order_value(key))
			end
		end
		if #unknown_keys > 0 then
			table.sort(unknown_keys)
			-- Bounded like the unknown-id warnings : the NUMBER of keys is attacker-controlled too.
			local extra = #unknown_keys - MAX_UNKNOWN_ORDER_WARNINGS
			if extra > 0 then
				for _ = 1, extra do
					table.remove(unknown_keys)
				end
				table.insert(unknown_keys, "and " .. extra .. " more")
			end
			return nil,
				"Unknown order key(s) "
					.. table.concat(unknown_keys, ", ")
					.. " for phase "
					.. shown_order_value(phase)
					.. " in plugin "
					.. plugin_id
					.. " (Allowed: after, before)"
		end
		-- Reused, not replaced : a manifest may spell the same phase twice (`header` and its
		-- `headers` alias) and Lua randomises the hash seed, so overwriting would drop one of
		-- the two -- a different one on every restart.
		local entry = declared[canonical_phase] or { before = {}, after = {} }
		for _, side in ipairs({ "before", "after" }) do
			local ids = constraints[side]
			if ids ~= nil then
				if not is_list(ids) then
					return nil,
						"Invalid order "
							.. side
							.. " for phase "
							.. shown_order_value(phase)
							.. " in plugin "
							.. plugin_id
							.. " (Must be a list of plugin ids)"
				end
				for _, id in ipairs(ids) do
					if not is_order_entry(id) then
						return nil,
							"Invalid order "
								.. side
								.. " entry "
								.. shown_order_value(id)
								.. " for phase "
								.. shown_order_value(phase)
								.. " in plugin "
								.. plugin_id
								.. " (Can only contain numbers, letters, underscores, dots and hyphens "
								.. '(min 1 characters and max 64), or the wildcard "*")'
					end
					table.insert(entry[side], id)
				end
			end
		end
		declared[canonical_phase] = entry
	end
	return declared
end

-- Stable topological sort (Kahn) of `list` under `edges` ({ from = id, to = id }). Among the
-- nodes that are ready, the one sitting earliest in `list` is always emitted first, so a phase
-- whose plugins declare nothing comes out exactly as the default list and the result does not
-- depend on the edge insertion order. Returns the sorted list, or nil plus the ids left in the
-- cycle (sorted, so the warning is reproducible).
local function stable_toposort(list, edges)
	local position, indegree, outgoing = {}, {}, {}
	for index, id in ipairs(list) do
		position[id] = index
		indegree[id] = 0
		outgoing[id] = {}
	end
	for _, edge in ipairs(edges) do
		table.insert(outgoing[edge.from], edge.to)
		indegree[edge.to] = indegree[edge.to] + 1
	end

	local ready = {}
	for _, id in ipairs(list) do
		if indegree[id] == 0 then
			table.insert(ready, id)
		end
	end

	local sorted = {}
	while #ready > 0 do
		local pick, pick_position = 1, position[ready[1]]
		for index = 2, #ready do
			if position[ready[index]] < pick_position then
				pick, pick_position = index, position[ready[index]]
			end
		end
		local id = table.remove(ready, pick)
		table.insert(sorted, id)
		for _, target in ipairs(outgoing[id]) do
			indegree[target] = indegree[target] - 1
			if indegree[target] == 0 then
				table.insert(ready, target)
			end
		end
	end

	if #sorted < #list then
		-- The nodes never emitted are the cycles themselves PLUS everything stuck downstream of
		-- them. Peel the ones that no longer point at a residual node until the set stops
		-- shrinking. What survives is every node on a cycle, plus any node that is both
		-- downstream of one cycle and points into another -- a bridge between two cycles is kept
		-- although it is on neither. Exactness would need Tarjan SCCs; the peel is deliberately
		-- the cheap version, because it is already exact for the single-cycle case (the only one
		-- a human writes by accident) and the bridge is only ever named, never mis-ordered.
		-- What matters is what it EXCLUDES : a plain downstream chain, which the round-1 version
		-- named and silently stripped of its own perfectly satisfiable declarations.
		local residual = {}
		for _, id in ipairs(list) do
			if indegree[id] > 0 then
				residual[id] = true
			end
		end
		local peeled = true
		while peeled do
			peeled = false
			for id in pairs(residual) do
				local reaches_residual = false
				for _, target in ipairs(outgoing[id]) do
					if residual[target] then
						reaches_residual = true
						break
					end
				end
				if not reaches_residual then
					residual[id] = nil
					peeled = true
				end
			end
		end
		local cycle = {}
		for _, id in ipairs(list) do
			if residual[id] then
				table.insert(cycle, id)
			end
		end
		table.sort(cycle)
		return nil, cycle
	end
	return sorted
end

-- `"*"` inside a declared before/after list means "every other plugin implementing this phase
-- that is not itself constrained relative to me". Two plugins that wave the same wildcard in the
-- same direction (`before *` vs `before *`, or `after *` vs `after *`) have nothing to arbitrate,
-- so no edge is added between them and the default list order stands -- a `before *` vs `after *`
-- pair is trivially consistent (both independently want the same edge). A plugin that names me
-- explicitly on the SAME side (e.g. another plugin's own `before` list names me) always wins over
-- my wildcard : the wildcard edge towards it is simply skipped, no cycle, explicit beats wildcard.
-- Only an OPPOSITE-side self-contradiction cycles : my own `before: ["*"]` plus my own
-- `after: [x]` for the same phase produces both `id -> x` (from the wildcard) and `x -> id` (from
-- the explicit `after`), a genuine 2-node cycle caught by the existing cycle machinery -- no
-- separate wildcard-contradiction check is needed.
--
-- Consults `constrained` (the phase's full declared-order map), not the caller's `skip` set : a
-- pin's exemption is evaluated against what every other plugin in the phase actually declared, not
-- against which of them survived an unrelated cycle elsewhere in the same phase. In the rare case
-- of a wildcard plugin sharing a phase with a *different* cycle, this can make a pin skip one edge
-- it did not strictly need to (never a wrong order, never a new cycle -- `wildcard_edges` is a pure
-- function of its arguments, so the retry's edge set is always a subset of the first pass's, and
-- every wildcard edge still has its declarer as an endpoint, so the "both endpoints are in `cycle`"
-- argument for the single retry still holds).
local function wildcard_edges(id, side, list, constrained)
	local edges = {}
	for _, other_id in ipairs(list) do
		if other_id ~= id then
			local other_entry = constrained[other_id]
			local other_side = other_entry and other_entry[side]
			local skip = false
			if other_side then
				for _, value in ipairs(other_side) do
					if value == "*" or value == id then
						skip = true
						break
					end
				end
			end
			if not skip then
				if side == "before" then
					table.insert(edges, { from = id, to = other_id })
				else
					table.insert(edges, { from = other_id, to = id })
				end
			end
		end
	end
	return edges
end

helpers.order_plugins = function(plugins, variables)
	-- Extract default orders
	local file, err, nb = open("/usr/share/bunkerweb/core/order.json", "r")
	if not file then
		return false, err .. " (nb = " .. tostring(nb) .. ")"
	end
	local ok, orders = pcall(decode, file:read("*a"))
	file:close()
	if not ok then
		return false, "invalid order.json : " .. err
	end

	-- Map legacy keys to phases
	local phase_aliases = { headers = "header" }
	local phases = get_phases()
	local phases_set = {}
	local default_orders = {}
	for _, phase in ipairs(phases) do
		default_orders[phase] = {}
		phases_set[phase] = true
	end
	for phase, order in pairs(orders) do
		local canonical_phase = phase_aliases[phase] or phase
		if default_orders[canonical_phase] then
			for _, id in ipairs(order) do
				table.insert(default_orders[canonical_phase], id)
			end
		end
	end

	-- Warnings are returned to the caller rather than logged here : helpers has no logger, and the
	-- two init confs already own the reporting of the PLUGINS_ORDER_* misses.
	local order_warnings = {}

	-- Compute plugins/id/phases table
	local plugins_phases = {}
	local plugin_lookup = {}
	local declared_orders = {}
	for _, plugin in ipairs(plugins) do
		plugins_phases[plugin.id] = {}
		plugin_lookup[plugin.id] = true
		for _, phase in ipairs(plugin.phases) do
			plugins_phases[plugin.id][phase] = true
		end
		if plugin.order ~= nil then
			local declared, order_err = parse_declared_order(plugin.id, plugin.order, phases_set, phase_aliases)
			if declared then
				declared_orders[plugin.id] = declared
			else
				-- Same tail as Configurator's warning, so an operator grepping one finds the other.
				table.insert(order_warnings, order_err .. ", ignoring the order declaration")
			end
		end
	end

	-- Default list for a phase : PRO first, then external, then core in order.json order, then
	-- the core plugins order.json doesn't name, alphabetically. Before 1.7 every non-core plugin
	-- landed in the alphabetical tail, which is why PRO acme used to rewrite the computed order.
	local function build_default_list(phase)
		local buckets = { {}, {}, {} }
		local bucketed = {}
		for _, plugin in ipairs(plugins) do
			local id = plugin.id
			if not bucketed[id] and plugins_phases[id] and plugins_phases[id][phase] then
				bucketed[id] = true
				table.insert(buckets[ORIGIN_RANK[plugin.type] or ORIGIN_RANK.core], id)
			end
		end
		table.sort(buckets[1])
		table.sort(buckets[2])

		local list = {}
		for rank = 1, 2 do
			for _, id in ipairs(buckets[rank]) do
				table.insert(list, id)
			end
		end

		local core_left = {}
		for _, id in ipairs(buckets[3]) do
			core_left[id] = true
		end
		for _, id in ipairs(default_orders[phase]) do
			if core_left[id] then
				core_left[id] = nil
				table.insert(list, id)
			end
		end
		local rest = {}
		for _, id in ipairs(buckets[3]) do
			if core_left[id] then
				table.insert(rest, id)
			end
		end
		table.sort(rest)
		for _, id in ipairs(rest) do
			table.insert(list, id)
		end
		return list
	end

	-- Apply the plugins' own declarations to a phase's default list.
	local function apply_declared_order(phase, list)
		local in_phase = {}
		for _, id in ipairs(list) do
			in_phase[id] = true
		end

		local constrained = {}
		for _, id in ipairs(list) do
			local entry = declared_orders[id] and declared_orders[id][phase]
			if entry then
				-- Capped and deduplicated per (plugin, phase) : one line per unknown id, uncapped,
				-- meant a manifest naming 200 000 ids wrote 27.5 MB of error.log per phase per
				-- configuration load, and a load happens on every reload (SEC F-10).
				local seen_unknown, unknown_count = {}, 0
				for _, side in ipairs({ "before", "after" }) do
					for _, other in ipairs(entry[side]) do
						-- "*" is the wildcard token, not a plugin id : never reported as missing.
						if other ~= "*" and not in_phase[other] and not seen_unknown[other] then
							seen_unknown[other] = true
							unknown_count = unknown_count + 1
							if unknown_count <= MAX_UNKNOWN_ORDER_WARNINGS then
								table.insert(
									order_warnings,
									"plugin "
										.. id
										.. " declares order."
										.. phase
										.. "."
										.. side
										.. " = "
										.. other
										.. " but that plugin is not available or doesn't implement the phase, ignoring it"
								)
							end
						end
					end
				end
				if unknown_count > MAX_UNKNOWN_ORDER_WARNINGS then
					table.insert(
						order_warnings,
						"plugin "
							.. id
							.. " declares "
							.. (unknown_count - MAX_UNKNOWN_ORDER_WARNINGS)
							.. " more unknown order id(s) for phase "
							.. phase
							.. ", not listing them"
					)
				end
				constrained[id] = entry
			end
		end
		if next(constrained) == nil then
			return list
		end

		local function edges_for(skip)
			local edges = {}
			for id, entry in pairs(constrained) do
				if not skip[id] then
					for _, side in ipairs({ "before", "after" }) do
						local has_wildcard = false
						for _, other in ipairs(entry[side]) do
							if other == "*" then
								has_wildcard = true
							elseif in_phase[other] then
								if side == "before" then
									table.insert(edges, { from = id, to = other })
								else
									table.insert(edges, { from = other, to = id })
								end
							end
						end
						if has_wildcard then
							for _, edge in ipairs(wildcard_edges(id, side, list, constrained)) do
								table.insert(edges, edge)
							end
						end
					end
				end
			end
			return edges
		end

		local sorted, cycle = stable_toposort(list, edges_for({}))
		if sorted then
			return sorted
		end
		if #cycle == 0 then
			-- Unreachable : a stalled Kahn always leaves at least one node on a cycle. Bail out to
			-- the default list rather than retry with an empty skip set, which would stall again.
			table.insert(order_warnings, "unresolvable order for phase " .. phase .. " : keeping the default order")
			return list
		end
		if #cycle == 1 then
			table.insert(
				order_warnings,
				"plugin "
					.. cycle[1]
					.. " declares itself before or after itself in phase "
					.. phase
					.. " : dropping its order declarations for this phase"
			)
		else
			table.insert(
				order_warnings,
				"order cycle for phase "
					.. phase
					.. " between "
					.. table.concat(cycle, ", ")
					.. " : dropping the order declarations of these plugins for this phase"
			)
		end
		-- Every edge on a cycle is declared by one of its two endpoints, and both endpoints are in
		-- `cycle`, so skipping their declarations cuts every cycle edge. Dropping edges can never
		-- create a new cycle, hence a single retry is enough -- and every plugin outside the cycle
		-- keeps its own, perfectly satisfiable, declarations.
		local skip = {}
		for _, id in ipairs(cycle) do
			skip[id] = true
		end
		sorted = stable_toposort(list, edges_for(skip))
		return sorted or list
	end

	local phase_defaults = {}
	for _, phase in ipairs(phases) do
		phase_defaults[phase] = apply_declared_order(phase, build_default_list(phase))
	end

	-- Collect overrides (global + per-site for multisite-aware phases)
	local overrides = { global = {} }
	local global_variables = variables and variables["global"] or variables or {}
	for _, phase in ipairs(phases) do
		local key = "PLUGINS_ORDER_" .. phase:upper()
		overrides.global[phase] = parse_override(global_variables[key])
	end

	local per_site_overrides = {}
	if variables then
		for server_name, vars in pairs(variables) do
			if server_name ~= "global" then
				per_site_overrides[server_name] = {}
				for _, phase in ipairs(phases) do
					local key = "PLUGINS_ORDER_" .. phase:upper()
					per_site_overrides[server_name][phase] = parse_override(vars[key])
				end
			end
		end
	end

	-- Order result. The operator override keeps the last word : it is prepended, everything else
	-- follows in the (already resolved) default order.
	local function build_order(override_set)
		local build_orders = {}
		local missing = {}
		for _, phase in ipairs(phases) do
			build_orders[phase] = {}
			missing[phase] = {}

			local seen = {}

			for _, id in ipairs(override_set[phase] or {}) do
				if not seen[id] and plugin_lookup[id] and plugins_phases[id] and plugins_phases[id][phase] then
					table.insert(build_orders[phase], id)
					seen[id] = true
				elseif not seen[id] then
					missing[phase][id] = true
				end
			end

			for _, id in ipairs(phase_defaults[phase]) do
				if not seen[id] then
					table.insert(build_orders[phase], id)
					seen[id] = true
				end
			end
		end
		return build_orders, missing
	end

	-- Global order (backward compatible keys at root)
	local global_orders, global_missing = build_order(overrides.global)
	local result_orders = {}
	for phase, ids in pairs(global_orders) do
		result_orders[phase] = ids
	end
	result_orders.global = global_orders

	-- Per-site orders (only if overrides exist)
	local per_site_orders = {}
	local per_site_missing = {}
	for server_name, override_set in pairs(per_site_overrides) do
		local server_name_orders, missing = build_order(override_set)
		per_site_orders[server_name] = server_name_orders
		per_site_missing[server_name] = missing
	end
	result_orders.per_site = per_site_orders

	-- Merge missing maps for reporting (global + per-site)
	local missing_plugins = { global = global_missing, per_site = per_site_missing }

	return true, result_orders, missing_plugins, order_warnings
end

helpers.require_plugin = function(id)
	-- Require call
	local ok, plugin_lua = pcall(require, id .. "/" .. id)
	if not ok then
		if plugin_lua:match("not found") then
			return nil, "plugin " .. id .. " doesn't have LUA code"
		end
		return false, "require error for plugin " .. id .. " : " .. plugin_lua
	end
	-- New call
	if plugin_lua.new == nil then
		return false, "missing new() method for plugin " .. id
	end
	-- Return plugin
	return plugin_lua, "require() call successful for plugin " .. id
end

helpers.new_plugin = function(plugin_lua, ctx)
	-- Require call
	local ok, plugin_obj = pcall(plugin_lua.new, plugin_lua, ctx)
	if not ok then
		return false, "new error for plugin " .. plugin_lua.name .. " : " .. plugin_obj
	end
	return true, plugin_obj
end

-- Every phase conf (access, log, header, set, preread, ssl_certificate, init, init_worker)
-- and api.lua reach plugin code through call_plugin, so this is the one place that can time
-- every plugin in every phase. Returns false outside a request: init/init_worker have no ctx.
helpers.timings_enabled = function(plugin)
	if not (plugin.ctx and plugin.ctx.bw) then
		return false
	end
	if collect_timings == nil then
		collect_timings = get_variable("METRICS_COLLECT_TIMINGS", false) == "yes"
	end
	return collect_timings
end

helpers.call_plugin = function(plugin, method)
	-- Check if method is present
	if plugin[method] == nil then
		return nil, "missing " .. method .. "() method for plugin " .. plugin:get_id()
	end
	-- Call method. ngx.now() alone reads NGINX's cached time, which only advances when the
	-- event loop yields -- a CPU-bound plugin would measure exactly 0. update_time() forces
	-- the refresh; on Linux that is a vDSO gettimeofday (tens of nanoseconds), so the cost is
	-- ~1us per request across a full plugin chain. Gated all the same.
	local timed = helpers.timings_enabled(plugin)
	local started
	if timed then
		update_time()
		started = now()
	end
	local ok, ret = pcall(plugin[method], plugin)
	if timed then
		update_time()
		-- Recorded even when the call failed: a plugin that blows up after a slow upstream
		-- is exactly the one worth seeing in the timings.
		plugin:set_metric("timers", method, now() - started)
	end
	if not ok then
		return false, plugin:get_id() .. ":" .. method .. "() failed : " .. ret
	end
	if ret == nil then
		return false, plugin:get_id() .. ":" .. method .. "() returned nil value"
	end
	-- Check values
	local missing_values = {}
	local required_values = { "ret", "msg" }
	for _, value in ipairs(required_values) do
		if ret[value] == nil then
			table.insert(missing_values, value)
		end
	end
	if #missing_values > 0 then
		return false, "missing required return value(s) : " .. encode(missing_values)
	end
	-- Return
	return true, ret
end

helpers.fill_ctx = function(no_ref)
	-- Return errors as table
	local errors = {}
	-- Try to load saved ctx
	local request = get_request()
	if no_ref ~= true and request then
		apply_ref()
	end
	local ctx = ngx.ctx
	-- Check if ctx is already filled
	if not ctx.bw then
		-- Instantiate bw table
		local data = {}
		if request then
			-- Common vars
			data.kind = "http"
			if subsystem == "stream" then
				data.kind = "stream"
			end
			data.remote_addr = var.remote_addr
			data.server_name = var.server_name
			data.time_local = var.time_local
			if data.kind == "http" then
				data.uri = var.uri
				data.request_id = var.request_id
				data.request_uri = var.request_uri
				data.request_method = var.request_method
				data.http_user_agent = var.http_user_agent
				data.http_host = var.http_host
				data.http_content_type = var.http_content_type
				data.http_content_length = var.http_content_length
				data.http_origin = var.http_origin
				data.http_accept = var.http_accept
				data.http_referer = var.http_referer
				data.http_version = req.http_version()
				data.start_time = req.start_time()
				data.scheme = var.scheme
			else
				-- Stream exposes no $request_id, $request_uri or $request_method. request_id is half
				-- of the (instance_hostname, request_id) dedup key, so it must exist; method and url
				-- are synthesized for the plugins that branch on them in stream (workflows
				-- conditions, badbehavior), NOT for storage — Reports keeps them null on a stream
				-- row and records the protocol and the L4 fields instead. `uri` is deliberately left
				-- nil : several plugins (country, limit) branch on it, and filling it would silently
				-- change what they match in stream.
				data.request_id = rand(32)
				data.start_time = req.start_time()
				data.request_method = upper(var.protocol or "TCP")
				data.request_uri = lower(data.request_method)
					.. "://"
					.. (var.server_name or "")
					.. ":"
					.. (var.server_port or "")
			end
			-- IP data : global
			local ip_global, err = ip_is_global(data.remote_addr)
			if ip_global == nil then
				table.insert(errors, "can't check if IP is global : " .. err)
			else
				data.ip_is_global = ip_global
			end
			-- IP data : v4 / v6
			data.ip_is_ipv4 = is_ipv4(data.remote_addr)
			data.ip_is_ipv6 = is_ipv6(data.remote_addr)
			if data.ip_is_ipv4 then
				data.ip_version = 4
			elseif data.ip_is_ipv6 then
				data.ip_version = 6
			end
			-- Normalized protocol : http/https or tcp/udp
			if data.kind == "http" then
				data.protocol = data.scheme
			elseif var.protocol then
				data.protocol = lower(var.protocol)
			end
			-- Geo data : resolved once here, then shared by plugins, logs and workflows
			if data.ip_is_global then
				local country, country_err = get_country(data.remote_addr)
				if country then
					data.country = country
					data.country_ok = true
				else
					data.country = "unknown"
					data.country_ok = false
					if not geo_country_warned then
						geo_country_warned = true
						table.insert(errors, "can't get country of IP : " .. tostring(country_err))
					end
				end
				local asn_number, asn_org, asn_err = get_asn(data.remote_addr)
				if asn_number then
					data.asn_number = asn_number
					data.asn_org = asn_org
					data.asn_ok = true
				else
					data.asn_ok = false
					if not geo_asn_warned then
						geo_asn_warned = true
						table.insert(errors, "can't get ASN of IP : " .. tostring(asn_err))
					end
				end
				local city, city_err = get_city(data.remote_addr)
				if city then
					data.city = city
				elseif city == nil and not geo_city_warned then
					-- false means the optional city database is simply absent, which is the
					-- default : only a real lookup failure is worth reporting
					geo_city_warned = true
					table.insert(errors, "can't get city of IP : " .. tostring(city_err))
				end
				-- false means the database is absent, a known state unlike a nil failure
				data.city_ok = city ~= nil
			else
				-- Non-global IP : "local", "no ASN" and "no city" are facts, not resolution failures
				data.country = "local"
				data.country_ok = true
				data.asn_ok = true
				data.city_ok = true
			end
		end
		-- Fill ctx
		ctx.bw = data
	end
	-- Always create new objects for current phases in case of cosockets
	local use_redis, err = get_variable("USE_REDIS", false)
	if not use_redis then
		table.insert(errors, "can't get variable from datastore : " .. err)
	end
	ctx.bw.internalstore =
		require "bunkerweb.datastore":new(subsystem == "http" and shared.internalstore or shared.internalstore_stream)
	ctx.bw.datastore = require "bunkerweb.datastore":new()
	ctx.bw.clusterstore = require "bunkerweb.clusterstore":new()
	ctx.bw.cachestore = require "bunkerweb.cachestore":new(use_redis == "yes", ctx)
	return true, "ctx filled", errors, ctx
end

-- Copy the enriched ctx to the $bw_* NGINX variables (logs, custom configs).
-- Only call it from a phase where writing ngx.var is allowed (set, preread) and from a server
-- block declaring the variables : server-http/server.conf and server-stream/server-stream.conf.
helpers.export_ctx_vars = function(ctx)
	local data = ctx and ctx.bw
	if not data then
		return
	end
	-- Writing an undeclared variable raises, and this runs on every request : a BunkerWeb instance
	-- upgraded before it receives the matching configuration would answer 500 to all traffic.
	-- Logging is left to the caller so a version skew degrades the logs, never the request.
	local ok, err = pcall(function()
		var.bw_kind = data.kind or ""
		var.bw_protocol = data.protocol or ""
		var.bw_ip_is_global = data.ip_is_global and "yes" or "no"
		var.bw_ip_version = data.ip_version and tostring(data.ip_version) or ""
		var.bw_country = data.country or ""
		var.bw_city = data.city or ""
		var.bw_asn_number = data.asn_number and tostring(data.asn_number) or ""
		var.bw_asn_org = data.asn_org or ""
	end)
	if not ok and not export_vars_warned then
		export_vars_warned = true
		return false, "can't export the context to the $bw_* variables : " .. tostring(err)
	end
	return ok
end

helpers.save_ctx = function(ctx)
	if get_request() then
		stash_ref(ctx)
	end
end

function helpers.load_variables(all_variables, plugins)
	-- Extract settings from plugins and global ones
	local all_settings = {}
	for _, plugin in ipairs(plugins) do
		if plugin.settings then
			for setting, data in pairs(plugin.settings) do
				all_settings[setting] = data
			end
		end
	end
	local file = open("/usr/share/bunkerweb/settings.json")
	if not file then
		return false, "can't open settings.json"
	end
	local ok, settings = pcall(decode, file:read("*a"))
	file:close()
	if not ok then
		return false, "invalid settings.json : " .. settings
	end
	for setting, data in pairs(settings) do
		all_settings[setting] = data
	end

	-- Initialize variables structure
	local variables = { ["global"] = {} }
	local multisite = all_variables["MULTISITE"] == "yes"
	local server_names = {}
	if multisite then
		for server_name in all_variables["SERVER_NAME"]:gmatch("%S+") do
			variables[server_name] = {}
			table.insert(server_names, server_name)
		end
	end

	-- Pre-compile patterns for better performance
	local escaped_server_names = {}
	if multisite then
		for _, server_name in ipairs(server_names) do
			escaped_server_names[server_name] = server_name:gsub("([^%w])", "%%%1")
		end
	end

	-- Single pass through all_variables
	for variable, value in pairs(all_variables) do
		-- Check for direct global settings first
		if all_settings[variable] then
			variables["global"][variable] = value
		end

		-- Handle multisite and multiple settings in one pass
		if multisite then
			-- Try to match server-specific variables
			for _, server_name in ipairs(server_names) do
				local escaped_server_name = escaped_server_names[server_name]
				local setting = variable:match("^" .. escaped_server_name .. "_(.+)$")
				if setting then
					-- Check if it's a direct setting
					if all_settings[setting] then
						variables[server_name][setting] = value
					-- Check if it's a multiple setting
					elseif setting:match("^(.+)_%d+$") then
						local base_setting = setting:match("^(.+)_%d+$")
						if all_settings[base_setting] and all_settings[base_setting].multiple then
							variables[server_name][setting] = value
						end
					end
				end
			end
		end

		-- Handle multiple settings for global
		local base_setting = variable:match("^(.+)_%d+$")
		if base_setting and all_settings[base_setting] and all_settings[base_setting].multiple then
			variables["global"][variable] = value
		end
	end

	return true, variables
end

return helpers
