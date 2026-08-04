local cjson = require "cjson"
local class = require "middleclass"
local eval = require "workflows.eval"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local ratelimit = require "bunkerweb.ratelimit"
local utils = require "bunkerweb.utils"

local workflows = class("workflows", plugin)

local ngx = ngx
local ERR = ngx.ERR
local re_find = ngx.re.find
local open = io.open
local sort = table.sort
local sub = string.sub
local tonumber = tonumber
local decode = cjson.decode
local NULL = cjson.null
local get_variable = utils.get_variable
local get_deny_status = utils.get_deny_status
local get_security_mode = utils.get_security_mode
local is_whitelisted = utils.is_whitelisted
local set_reason = utils.set_reason
local ratelimit_incr = ratelimit.incr
local ipmatcher_new = ipmatcher.new
local run = eval.run
local F, T, U = eval.FALSE, eval.TRUE, eval.UNKNOWN
local COMBINATORS = { all = eval.ALL, any = eval.ANY, ["not"] = eval.NOT }

-- Artefact compiled by the control plane and shipped with the ordinary cache push.
local ARTEFACT = "/var/cache/bunkerweb/workflows/config.json"

-- NGINX shares one regex cache (lua_regex_cache_max_entries, 1024 per worker by default)
-- between every plugin that compiles with the "o" flag — blacklist, greylist, dnsbl,
-- antibot, limit, country. Overflowing it does not raise: ngx.re silently recompiles on
-- every call, an instance-wide CPU cliff with nothing pointing at the cause. So the budget
-- is enforced here, at init, by counting; the excess degrades to UNKNOWN, which can only
-- ever make a rule not match — never make one match by accident.
local DEFAULT_REGEX_BUDGET = 512

-- Prepared plan, built once in the init phase — which runs in the master before the workers
-- fork, so every worker inherits it — and never touched again. Module-level rather than in
-- a shared dict on purpose: the compiled predicates are closures and matchers, which cannot
-- round-trip through serialization, and a per-request lookup would cost more than the
-- evaluation itself.
local PLAN = { services = {}, workflows = {} }

local function set_of(values)
	local set = {}
	for _, value in ipairs(values or {}) do
		set[value] = true
	end
	return set
end

local function always(value)
	return function()
		return value
	end
end

-- One matcher per distinct value list, so a group referenced by twenty rules is built once
-- and every leaf points at the same closure upvalue.
local function ip_predicate(values, logger)
	local matcher, err = ipmatcher_new(values)
	if not matcher then
		logger:log(ERR, "workflow rule holds an unusable IP list (" .. tostring(err) .. "), it will never match")
		return always(U)
	end
	return function(bw)
		local matched, match_err = matcher:match(bw.remote_addr)
		if match_err then
			return U
		end
		return matched and T or F
	end
end

local function country_predicate(values)
	local set = set_of(values)
	return function(bw)
		-- country_ok distinguishes a resolved country from a broken or missing database.
		if not bw.country_ok then
			return U
		end
		return set[bw.country] and T or F
	end
end

local function asn_predicate(values)
	local set = set_of(values)
	return function(bw)
		if not bw.asn_ok then
			return U
		end
		-- A private IP resolves fine and simply has no ASN : that is a FACT, so FALSE, not
		-- UNKNOWN. Conflating the two would let "NOT in these ASNs" match local traffic.
		if not bw.asn_number then
			return F
		end
		return set[bw.asn_number] and T or F
	end
end

local function method_predicate(values)
	local set = set_of(values)
	return function(bw)
		return set[bw.request_method] and T or F
	end
end

-- Every builder is called as ``builder(values, logger)``; the two that cannot fail simply
-- ignore the second argument.
local KIND_PREDICATES = {
	ip = ip_predicate,
	country = country_predicate,
	asn = asn_predicate,
}

-- Compilation state for one plan build.
local function new_state(logger, budget)
	return { logger = logger, budget = budget, regexes = 0, dropped = 0 }
end

local function uri_predicate(node, state)
	local value = node.value
	if node.match == "exact" then
		return function(bw)
			return bw.uri == value and T or F
		end
	end
	if node.match == "prefix" then
		local length = #value
		return function(bw)
			return sub(bw.uri, 1, length) == value and T or F
		end
	end

	state.regexes = state.regexes + 1
	if state.regexes > state.budget then
		state.dropped = state.dropped + 1
		return always(U)
	end
	-- Probe once here rather than letting utils.regex_match log an ERR on every failing
	-- call : a bad pattern on a hot path is a log flood, not a diagnosis.
	local _, _, err = re_find("", value, "jo")
	if err then
		state.logger:log(ERR, "workflow rule holds an invalid regex (" .. tostring(err) .. "), it will never match")
		return always(U)
	end
	return function(bw)
		local from, _, find_err = re_find(bw.uri, value, "jo")
		if find_err then
			return U
		end
		return from and T or F
	end
end

local function compile_node(node, groups, state)
	local op = node.op
	local combinator = COMBINATORS[op]
	if combinator == eval.NOT then
		return { op = combinator, compile_node(node.node, groups, state) }
	end
	if combinator then
		local compiled = { op = combinator }
		for index, child in ipairs(node.nodes) do
			compiled[index] = compile_node(child, groups, state)
		end
		return compiled
	end

	if op == "uri" then
		return { f = uri_predicate(node, state) }
	end
	if op == "method" then
		return { f = method_predicate(node.values) }
	end
	if op == "group" then
		local group = groups[node.group_id]
		local builder = KIND_PREDICATES[node.kind]
		if not group or not builder then
			-- The compiler refuses to ship this, so reaching it means the artefact was
			-- hand-edited. Never matching is the safe reading of "I cannot tell".
			state.logger:log(ERR, "workflow rule references an unusable group, it will never match")
			return { f = always(U) }
		end
		return { f = builder(group[node.kind] or {}, state.logger) }
	end
	local builder = KIND_PREDICATES[op]
	if not builder then
		state.logger:log(ERR, "workflow rule holds an unknown condition " .. tostring(op) .. ", it will never match")
		return { f = always(U) }
	end
	return { f = builder(node.values, state.logger) }
end

function workflows:initialize(ctx)
	plugin.initialize(self, "workflows", ctx)
end

function workflows:init()
	PLAN = { services = {}, workflows = {} }

	local file = open(ARTEFACT, "r")
	if not file then
		-- Fail-open. An instance that has not received the artefact yet — first boot, or a
		-- push that never arrived — must keep serving traffic under its ordinary
		-- protections. A policy layer that locks everyone out when its own data is missing
		-- is worse than one that is briefly absent.
		return self:ret(true, "no workflow artefact yet, no policy applied")
	end
	local content = file:read("*a")
	file:close()

	local ok, artefact = pcall(decode, content)
	if not ok or type(artefact) ~= "table" then
		-- One error at load, never one per request.
		return self:ret(false, "the workflow artefact is unreadable, no policy applied")
	end

	local budget = tonumber(get_variable("WORKFLOWS_REGEX_BUDGET", false) or "") or DEFAULT_REGEX_BUDGET
	local state = new_state(self.logger, budget)
	local groups = artefact.groups or {}

	-- Compiled in sorted id order, never in pairs() order. The regex budget above is spent as
	-- this loop walks, so an unspecified order means two instances loading a byte-identical
	-- artefact can exhaust it against different rules and end up with a different set degraded
	-- to UNKNOWN — and a rule that can never match is a security control that is silently off.
	local workflow_ids = {}
	for workflow_id in pairs(artefact.workflows or {}) do
		workflow_ids[#workflow_ids + 1] = workflow_id
	end
	sort(workflow_ids)

	local count = 0
	for _, workflow_id in ipairs(workflow_ids) do
		local workflow = artefact.workflows[workflow_id]
		local rules = {}
		for index, rule in ipairs(workflow.rules or {}) do
			rules[index] = {
				id = rule.id,
				-- Full store prefix built here so the request path only appends the service
				-- and the client IP, which are the only parts that vary per request.
				counter = "plugin_workflows_" .. (rule.counter or (workflow_id .. "/" .. tostring(rule.id))),
				root = compile_node(rule.condition, groups, state),
				-- cjson decodes a JSON null to its own userdata sentinel, NOT to nil, and
				-- userdata is truthy — so a rule without a threshold would take the rate-gate
				-- branch and blow up indexing it. Normalise here, once, at load.
				threshold = rule.threshold ~= NULL and rule.threshold or nil,
				action = rule.action,
			}
		end
		PLAN.workflows[workflow_id] = { name = workflow.name, rules = rules }
		count = count + 1
	end

	local services = 0
	for server, order in pairs(artefact.services or {}) do
		PLAN.services[server] = order
		services = services + 1
	end

	if state.dropped > 0 then
		self.logger:log(
			ERR,
			"workflow regex budget of "
				.. tostring(budget)
				.. " exhausted : "
				.. tostring(state.dropped)
				.. " rule condition(s) disabled, use exact or prefix URI matches instead"
		)
	end

	return self:ret(true, "loaded " .. tostring(count) .. " workflow(s) for " .. tostring(services) .. " service(s)")
end

-- Run the single terminal action of the rule that won.
function workflows:apply(workflow, rule)
	local action = rule.action
	local data = { workflow = workflow.name, rule = rule.id, action = action.type }
	local security_mode = get_security_mode(self.ctx)
	self:set_metric("counters", "workflow_" .. action.type, 1)

	if security_mode ~= "block" then
		-- detect : same trees, same order, same counters, but nothing is enforced.
		-- Returning a status here would land in the dispatcher's detect branch, which
		-- *breaks* the loop — silently skipping antibot and every later access plugin. So
		-- the observation is recorded by hand and the chain is left to continue.
		set_reason("workflows", data, self.ctx, security_mode)
		return self:ret(true, "detected workflow " .. action.type .. " from rule " .. rule.id)
	end

	if action.type == "challenge" then
		-- Hand over to antibot, which runs immediately after: no status and no redirect, so
		-- the dispatcher keeps walking the chain instead of terminating here.
		self.ctx.bw.workflow_antibot_provider = action.provider
		return self:ret(true, "workflow rule " .. rule.id .. " requests the " .. action.provider .. " challenge")
	end

	if action.type == "redirect" then
		-- The dispatcher calls set_reason on its deny branch but *not* on its redirect
		-- branch, so without this the redirect never reaches the reports pipeline.
		set_reason("workflows", data, self.ctx, security_mode)
		return self:ret(true, "workflow rule " .. rule.id .. " redirects", action.status, action.url, data)
	end

	-- Deny status by default; a rule whose whole purpose is capping a rate may ask for 429.
	-- Both are in the dispatcher's reason_statuses, so it records the reason itself.
	return self:ret(true, "workflow rule " .. rule.id .. " blocks", action.status or get_deny_status(), nil, data)
end

function workflows:access()
	local order = PLAN.services[self.ctx.bw.server_name]
	if not order then
		-- The common case at scale : one hash lookup on a module upvalue, then out.
		return self:ret(true, "no workflow attached to this service")
	end
	-- The global whitelist keeps priority over every policy, as it does for the other
	-- access plugins.
	if is_whitelisted(self.ctx) then
		return self:ret(true, "client is whitelisted")
	end

	local bw = self.ctx.bw
	for _, workflow_id in ipairs(order) do
		local workflow = PLAN.workflows[workflow_id]
		if workflow then
			for _, rule in ipairs(workflow.rules) do
				if run(rule.root, bw) == T then
					local threshold = rule.threshold
					if not threshold then
						return self:apply(workflow, rule)
					end
					-- The gate is only ever reached by a rule whose static tree already
					-- matched, so a rule narrowed by a CIDR or a country never allocates a
					-- counter for traffic it does not cover.
					local count, err = ratelimit_incr(
						self,
						rule.counter .. "_" .. bw.server_name .. "_" .. bw.remote_addr,
						threshold.window
					)
					if not count then
						-- A store failure makes the gate UNKNOWN : the rule loses and
						-- evaluation continues, rather than blocking on a Redis outage.
						self:log_throttled(ERR, "workflow_rate_gate", "workflow rate gate failed : " .. tostring(err))
					elseif count > threshold.count then
						return self:apply(workflow, rule)
					end
					-- Under the threshold the rule does not win, and evaluation continues
					-- with the next one — which is how "over 10r/m block, otherwise
					-- challenge" is expressed as two ordered rules.
				end
			end
		end
	end

	return self:ret(true, "no rule matched")
end

return workflows
