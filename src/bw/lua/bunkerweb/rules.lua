-- Composite (AND) rules, shared by greylist, whitelist and blacklist.
--
-- Grammar (fixed -- the UI builds against this exact shape):
--
--     <rule> := <term> ( " AND " <term> )*
--     <term> := [ "NOT " ] <kind> ":" <value>
--     <kind> := ip | country | asn | rdns | ua | uri      ("user_agent" is an alias of "ua")
--
-- A rule matches only when EVERY term matches; rules are OR'd with each other and with the
-- plugin's flat lists, which still run first because they are cheaper and already cached.
--
-- Cache shape: per-TERM truth, never per-rule verdict. The key is (kind, value, subject),
-- so a handful of rules sharing one `ip:` term pay for it once, and `NOT` is applied by the
-- fold in evaluate() -- outside the cached value. That is what makes two rules with opposite
-- verdicts over the same term unable to poison each other. Measured against the per-rule
-- shape on a realistic workload (1000 requests, 20 IPs, 50 URIs, 5 rules sharing an ip term):
-- 106 matcher invocations and 106 cache keys instead of 2100 and 1200.
--
-- There is no escaping syntax: a value may not contain " and " in any casing, because that is
-- the separator. parse() refuses such a rule, and so does the setting's own regex at save time.

local ipmatcher = require "resty.ipmatcher"
local utils = require "bunkerweb.utils"

local rules = {}

local ngx = ngx
local ERR = ngx.ERR
local ipmatcher_new = ipmatcher.new
local get_rdns = utils.get_rdns
local rdns_forward_confirmed = utils.rdns_forward_confirmed
local regex_match = utils.regex_match
local ipairs = ipairs
local tostring = tostring
local type = type

rules.SEPARATOR = " AND "
rules.NEGATION = "NOT "

local KINDS = { ip = true, country = true, asn = true, rdns = true, ua = true, uri = true }
local ALIASES = { user_agent = "ua" }

-- Kinds whose subject is the client IP. They are the ones stream mode can evaluate, and the
-- ones whose truth is cacheable per remote_addr.
local IP_SUBJECT_KINDS = { ip = true, country = true, asn = true, rdns = true }
rules.IP_SUBJECT_KINDS = IP_SUBJECT_KINDS

-- Kinds a stream service cannot evaluate: their subject does not exist there, so such a term is
-- UNKNOWN in stream (see match_term) and the rule holding it is dead there -- flagged by
-- warnings() when the configuration loads, never silently.
rules.HTTP_ONLY_KINDS = { ua = true, uri = true }

-- A group token expands to several values inside one term, joined with a comma for the kinds
-- whose values cannot contain one. The regex kinds (ua, uri) expand to an alternation instead
-- and are never split here -- a PCRE quantifier like {1,3} owns the comma.
local function split_values(value)
	local values = {}
	for item in value:gmatch("[^,]+") do
		item = item:match("^%s*(.-)%s*$")
		if item ~= "" then
			values[#values + 1] = item
		end
	end
	return values
end

--- Parse one rule into its terms.
-- @return terms (list of {negate, kind, value, values}) or nil, err
function rules.parse(text)
	if type(text) ~= "string" then
		return nil, "rule is not a string"
	end
	text = text:match("^%s*(.-)%s*$")
	if text == "" then
		return nil, "empty rule"
	end
	local terms = {}
	local rest = text
	while true do
		-- Non-greedy: split on the FIRST " AND ", so a trailing separator leaves an empty
		-- segment that fails the term check below instead of being dropped.
		local segment, tail = rest:match("^(.-) AND (.*)$")
		if not segment then
			segment, tail = rest, nil
		end
		local negate = false
		if segment:sub(1, #rules.NEGATION) == rules.NEGATION then
			negate = true
			segment = segment:sub(#rules.NEGATION + 1)
		end
		local kind, value = segment:match("^([%a_]+):(.*)$")
		if not kind then
			return nil, "invalid term '" .. segment .. "' (expected [NOT ]<kind>:<value>)"
		end
		-- No case folding: the setting's own regex spells the kinds in lowercase, so folding
		-- here would accept at runtime what the save path refuses -- two gates disagreeing.
		kind = ALIASES[kind] or kind
		if not KINDS[kind] then
			return nil, "unknown kind '" .. kind .. "' in term '" .. segment .. "'"
		end
		if value == "" then
			return nil, "empty value in term '" .. segment .. "'"
		end
		-- The separator is literal and there is no escaping syntax, so a value still holding
		-- one after the split is a mis-split: a dangling " AND ", a separator inside a regex,
		-- or the far likelier lowercase " and " typo -- which would otherwise leave the whole
		-- tail buried in one term's value and the rule silently dead. Any casing is refused,
		-- exactly like the setting's own regex does at save time. Matches the plugin.json
		-- `<LIST>_RULE` regex; changing one without the other lets a value through here that
		-- the save path refuses, or the reverse.
		-- Padded at the end only, so a trailing " and" is caught while a value that merely
		-- *starts* with "and" is not -- byte-for-byte what the setting's regex does.
		local lowered = value:lower() .. " "
		if lowered:find(" and ", 1, true) then
			return nil, "term '" .. segment .. "' contains the AND separator inside its value"
		end
		terms[#terms + 1] = {
			negate = negate,
			kind = kind,
			value = value,
			values = IP_SUBJECT_KINDS[kind] and split_values(value) or { value },
		}
		if not tail then
			break
		end
		rest = tail
	end
	return terms
end

-- Numeric suffix of a `<BASE>_<n>` name, 0 for the bare base. Rules are evaluated in the
-- operator's numbering so two workers agree on which rule matched first.
local function suffix_of(name)
	return tonumber(name:match("_(%d+)$")) or 0
end

--- Parse a whole numeric-suffix family out of a flat variable table.
-- @param vars table of variable name -> value (one scope of get_multiple_variables)
-- @param base base setting id, e.g. "GREYLIST_RULE"
-- @return list of {id, text, terms}, list of error strings
function rules.parse_family(vars, base)
	local parsed, errors = {}, {}
	if type(vars) ~= "table" then
		return parsed, errors
	end
	local names = {}
	for name, value in pairs(vars) do
		if type(value) == "string" and value:match("%S") and (name == base or name:match("^" .. base .. "_%d+$")) then
			names[#names + 1] = name
		end
	end
	table.sort(names, function(a, b)
		return suffix_of(a) < suffix_of(b)
	end)
	for _, name in ipairs(names) do
		local terms, err = rules.parse(vars[name])
		if terms then
			parsed[#parsed + 1] = { id = name, text = vars[name], terms = terms }
		else
			errors[#errors + 1] = name .. " : " .. err
		end
	end
	return parsed, errors
end

--- Merge the scopes of a stored rule set for one service.
-- Mirrors utils.get_variable: the global value of a key holds unless the service declared that
-- exact key, so a service adding GREYLIST_RULE_2 keeps the global GREYLIST_RULE_1 instead of
-- replacing the whole family with its own.
function rules.for_server(all_scopes, server_name)
	if type(all_scopes) ~= "table" then
		return {}
	end
	local merged = {}
	local function absorb(list)
		for _, rule in ipairs(list or {}) do
			merged[rule.id] = rule
		end
	end
	absorb(all_scopes.global)
	if server_name then
		absorb(all_scopes[server_name])
	end
	local out = {}
	for _, rule in pairs(merged) do
		out[#out + 1] = rule
	end
	table.sort(out, function(a, b)
		return suffix_of(a.id) < suffix_of(b.id)
	end)
	return out
end

--- Warnings for a parsed rule set: the shapes that are valid but surprising.
-- Emitted at INIT time, not at configuration generation: each plugin's init_rules() calls this
-- from init_by_lua, so the lines land in the *instance's* error.log at WARN level, not in the
-- scheduler's output. Note that channel is lossy during init_by_lua (a different subset of lines
-- is dropped each reload cycle), so a missing warning is not proof a rule is well-formed.
-- @return list of warning strings
function rules.warnings(parsed)
	local out = {}
	for _, rule in ipairs(parsed) do
		local http_only, all_negated = nil, true
		for _, term in ipairs(rule.terms) do
			if rules.HTTP_ONLY_KINDS[term.kind] then
				http_only = http_only or term.kind
			end
			if not term.negate then
				all_negated = false
			end
			-- Resource-group tokens are expanded during config generation. One still here
			-- means expansion did not run for it, and no matcher can ever match a literal
			-- "@name" -- same failure the country plugin reports for its own tokens.
			if term.value:sub(1, 1) == "@" then
				out[#out + 1] = rule.id
					.. " has an unexpanded group token "
					.. term.value
					.. " in a "
					.. term.kind
					.. ": term, so it can never match"
			end
		end
		if http_only then
			out[#out + 1] = rule.id
				.. " has a "
				.. http_only
				.. ": term, which a stream service cannot evaluate : the rule can never match in stream mode"
		end
		if all_negated then
			out[#out + 1] = rule.id .. " is made only of NOT terms, so it matches almost every request"
		end
	end
	return out
end

--- Cache key for one term's truth, or nil when the request has no subject for that kind.
-- Length-prefixed on the value so no value/subject pair can forge another term's key.
function rules.cache_key(term, ctx)
	local subject
	if IP_SUBJECT_KINDS[term.kind] then
		subject = ctx.bw.remote_addr
	elseif term.kind == "ua" then
		subject = ctx.bw.http_user_agent
	elseif term.kind == "uri" then
		subject = ctx.bw.uri
	end
	if not subject then
		return nil
	end
	return "rule_term:" .. term.kind .. ":" .. #term.value .. ":" .. term.value .. ":" .. subject
end

--- Evaluate one term against the request. No caching here -- see term_truth().
-- Three-valued on purpose: true, false, or nil for "this request cannot answer that question"
-- -- a ua:/uri: term in stream (fill_ctx leaves both nil there) or on a request with no
-- User-Agent, and any lookup that failed. nil is NOT false: `NOT ua:^curl` returning true
-- because there is no User-Agent to inspect would widen a whitelist rule on exactly the
-- traffic the operator could not see. evaluate() drops a rule holding an unknown term, before
-- negation, and term_truth() never caches one.
function rules.match_term(term, opts)
	local ctx = opts.ctx
	local kind = term.kind
	if kind == "ip" then
		local ipm, err = ipmatcher_new(term.values)
		if not ipm then
			if opts.logger then
				opts.logger:log(ERR, "invalid ip term '" .. term.value .. "' : " .. tostring(err))
			end
			return nil
		end
		local match, match_err = ipm:match(ctx.bw.remote_addr)
		if match_err then
			if opts.logger then
				opts.logger:log(ERR, "error while matching ip term '" .. term.value .. "' : " .. match_err)
			end
			return nil
		end
		return match == true
	elseif kind == "country" then
		-- fill_ctx() sets "local" for a non-global IP -- a definite answer, so a NOT term may
		-- rely on it -- and "unknown" when the lookup failed, which is not an answer at all.
		local country = ctx.bw.country
		if not country or country == "unknown" then
			return nil
		end
		country = country:upper()
		for _, value in ipairs(term.values) do
			if value:upper() == country then
				return true
			end
		end
		return false
	elseif kind == "asn" then
		if not ctx.bw.ip_is_global then
			return false
		end
		-- A global IP with no ASN means the lookup failed, unlike a private one which simply
		-- has none.
		local asn = ctx.bw.asn_number
		if not asn then
			return nil
		end
		asn = tostring(asn)
		for _, value in ipairs(term.values) do
			-- The flat ASN lists accept "AS12345" and "12345" alike (their regex is
			-- `^( *(ASN?)?\d+ *)*$`), so a rule term has to as well.
			if value:gsub("^[Aa][Ss][Nn]?", "") == asn then
				return true
			end
		end
		return false
	elseif kind == "rdns" then
		if opts.rdns_global and not ctx.bw.ip_is_global then
			return false
		end
		local rdns_list, err = get_rdns(ctx.bw.remote_addr, ctx, true)
		if not rdns_list then
			if opts.logger then
				opts.logger:log(ERR, "error while getting rdns : " .. tostring(err))
			end
			return nil
		end
		if opts.rdns_forward_confirm then
			return rdns_forward_confirmed(rdns_list, term.values, ctx, ctx.bw.remote_addr, opts.logger) ~= nil
		end
		-- Deny lists match the PTR without forward confirmation, exactly like their flat
		-- BLACKLIST_RDNS pass: spoofing a PTR into a blocklist is not an attack.
		for _, rdns in ipairs(rdns_list) do
			for _, suffix in ipairs(term.values) do
				if rdns:sub(-#suffix) == suffix then
					return true
				end
			end
		end
		return false
	elseif kind == "ua" then
		local ua = ctx.bw.http_user_agent
		if not ua then
			return nil
		end
		return regex_match(ua, term.value) ~= nil
	elseif kind == "uri" then
		local uri = ctx.bw.uri
		if not uri then
			return nil
		end
		return regex_match(uri, term.value) ~= nil
	end
	return nil
end

--- Truth of one term, through the per-term cache when the caller provides one.
function rules.term_truth(term, opts)
	local key = opts.cache_get and rules.cache_key(term, opts.ctx) or nil
	if key then
		local cached = opts.cache_get(key)
		if cached ~= nil then
			return cached
		end
	end
	local truth = rules.match_term(term, opts)
	-- An unknown is not a cacheable bool, and caching it as one would freeze a transient
	-- resolver failure into the answer for the next 24 hours.
	if key and opts.cache_set and truth ~= nil then
		opts.cache_set(key, truth)
	end
	return truth
end

--- Fold the rules: first one whose every term is true (NOT inverting that term) wins.
-- @return the matching rule ({id, text, terms}) or nil
function rules.evaluate(parsed, opts)
	for _, rule in ipairs(parsed) do
		local matched = true
		for _, term in ipairs(rule.terms) do
			local truth = rules.term_truth(term, opts)
			if truth == nil then
				-- Unknown, checked BEFORE negation: `not nil` is true in Lua, so folding it
				-- through NOT would turn "cannot tell" into "matched".
				matched = false
				break
			end
			if term.negate then
				truth = not truth
			end
			if not truth then
				matched = false
				break
			end
		end
		if matched then
			return rule
		end
	end
	return nil
end

return rules
