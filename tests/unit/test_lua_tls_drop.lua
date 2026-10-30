local root = arg[0]:match("^(.*)/tests/unit/") or "."
package.path = root .. "/src/bw/lua/?.lua;" .. package.path

local failures = 0
local reset
local function it(name, fn)
	reset()
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function new_dict()
	local data = {}
	local dict = { _data = data, last_ttl = {} }
	function dict.get(_, k)
		return data[k]
	end
	function dict.safe_set(_, k, v, ttl)
		data[k] = v
		dict.last_ttl[k] = ttl
		return true
	end
	function dict.safe_add(_, k, v, ttl)
		if data[k] ~= nil then
			return false, "exists"
		end
		data[k] = v
		dict.last_ttl[k] = ttl
		return true
	end
	function dict.incr(_, k, v, init)
		if data[k] == nil then
			if init == nil then
				return nil, "not found"
			end
			data[k] = init
		end
		data[k] = data[k] + v
		return data[k]
	end
	function dict.delete(_, k)
		data[k] = nil
	end
	return dict
end

-- ngx and the modules the ClientHello path reads, all installed before the module under test is required
local raw, fam, quic, ext_error, exited, logs, pp_addr, pp_error
local worker_id = 0
_G.ngx = {
	shared = { bans_meta = new_dict(), metrics_datastore = new_dict() },
	worker = {
		id = function()
			return worker_id
		end,
	},
	log = function(level, ...)
		logs[#logs + 1] = { level = level, msg = table.concat({ ... }) }
	end,
	exit = function(code)
		exited[#exited + 1] = code
	end,
	ERROR = -1,
	WARN = 5,
}
package.loaded["cjson"] = {
	encode = function(t)
		return string.format("%s|%s|%s", t.id, t.rank, t.epoch)
	end,
	decode = function(s)
		local id, rank, epoch = s:match("^(.-)|(%d+)|(%d+)$")
		return { id = id, rank = tonumber(rank), epoch = tonumber(epoch) }
	end,
}
package.loaded["resty.random"] = {
	bytes = function(n)
		return string.rep("\171", n)
	end,
}
package.loaded["resty.string"] = {
	to_hex = function(s)
		return (s:gsub(".", function(c)
			return string.format("%02x", c:byte())
		end))
	end,
}
package.loaded["ngx.ssl"] = {
	raw_client_addr = function()
		return raw, fam
	end,
	proxy_protocol_addr = function()
		if pp_error then
			return nil, "boom"
		end
		return pp_addr
	end,
}
-- Just enough of resty.ipmatcher: dotted IPv4 networks (/8, /16, /24 or a single address) and one IPv6 literal
package.loaded["resty.ipmatcher"] = {
	parse_ipv4 = function(text)
		local a, b, c, d = tostring(text):match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
		if not a then
			return false
		end
		return ((a * 256 + b) * 256 + c) * 256 + d
	end,
	-- inet_pton(AF_INET6): "::" compression and an embedded dotted tail, returned as four 32-bit words
	parse_ipv6 = function(text)
		local head, tail = text, nil
		local cut = text:find("::", 1, true)
		if cut then
			head, tail = text:sub(1, cut - 1), text:sub(cut + 2)
		end
		local function groups(part)
			local out = {}
			for g in (part == "" and "" or part .. ":"):gmatch("([^:]*):") do
				local a, b, c, d = g:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
				if a and (a .. b .. c .. d):find("%f[%d]0%d") then
					return nil -- inet_pton refuses leading zeros in the dotted tail
				elseif a then
					out[#out + 1] = a * 256 + b
					out[#out + 1] = c * 256 + d
				elseif g:match("^%x%x?%x?%x?$") then
					out[#out + 1] = tonumber(g, 16)
				else
					return nil
				end
			end
			return out
		end
		local words, rest = groups(head), groups(tail or "")
		if not words or not rest or #words + #rest > (cut and 7 or 8) or (not cut and #words ~= 8) then
			return false
		end
		for _ = 1, 8 - #words - #rest do
			words[#words + 1] = 0
		end
		for _, w in ipairs(rest) do
			words[#words + 1] = w
		end
		return {
			words[1] * 65536 + words[2],
			words[3] * 65536 + words[4],
			words[5] * 65536 + words[6],
			words[7] * 65536 + words[8],
		}
	end,
	new = function(networks)
		return {
			match = function(_, addr)
				for _, network in ipairs(networks) do
					local base, bits = network:match("^([%d%.]+)/?(%d*)$")
					local keep = ({ [""] = 4, ["8"] = 1, ["16"] = 2, ["24"] = 3 })[bits]
					local want, got = {}, {}
					for part in base:gmatch("%d+") do
						want[#want + 1] = part
					end
					for part in addr:gmatch("%d+") do
						got[#got + 1] = part
					end
					local same = true
					for i = 1, keep do
						same = same and want[i] == got[i]
					end
					if same then
						return true
					end
				end
				return false
			end,
		}
	end,
}
package.loaded["ngx.ssl.clienthello"] = {
	get_client_hello_ext = function(ext_type)
		assert(ext_type == 57, "only the QUIC transport parameters extension is probed")
		if ext_error then
			return nil, "boom"
		end
		return quic and "\0" or nil
	end,
}

local vars, var_error, bans, seen_ip, wl, wl_service_only, wl_args
local utils_stub = {
	get_variable = function(name)
		if var_error == name then
			return nil, "boom"
		end
		if vars[name] == nil then
			return nil, "not found"
		end
		return vars[name], "success"
	end,
	is_banned_local = function(ip)
		seen_ip = ip
		local ban = bans[ip]
		if ban then
			return true, ban.reason, ban.rank
		end
		return false, "not banned", nil
	end,
	is_ip_whitelisted = function(ip, service, opts)
		wl_args = { ip = ip, service = service, opts = opts }
		if wl == "error" then
			return nil, "boom"
		end
		if wl_service_only and service == nil then
			return true, "ip"
		end
		return wl == true, "ip"
	end,
}
package.loaded["bunkerweb.utils"] = utils_stub
local original_is_banned_local = utils_stub.is_banned_local

local banlease = require("bunkerweb.banlease")

local ip = "1.2.3.4"
local service = "svc.example.com"

reset = function()
	for _, dict in pairs(ngx.shared) do
		for k in pairs(dict._data) do
			dict._data[k] = nil
		end
		dict.last_ttl = {}
	end
	vars = { BANS_TLS_DROP_REASONS = "", USE_REDIS = "no", SECURITY_MODE = "block" }
	var_error, bans, seen_ip, wl, wl_service_only, wl_args = nil, {}, nil, false, false, nil
	raw, fam, quic, ext_error, exited, logs = "\1\2\3\4", "inet", false, false, {}, {}
	pp_addr, pp_error = nil, nil
	utils_stub.is_banned_local = original_is_banned_local
end

local function set_reasons(value)
	vars.BANS_TLS_DROP_REASONS = value
end
local function local_ban(reason, rank)
	bans[ip] = { reason = reason, rank = rank }
end
local function marker(id, rank, epoch, svc)
	assert(banlease.write_marker(svc or service, ip, id, rank, epoch, 30), "marker written")
end
local function decide(svc, proxy_protocol, real_ip, trusted)
	return banlease.tls_drop_decision(svc, proxy_protocol, real_ip, trusted)
end
local function d()
	return (decide(service, false, false))
end
local function d_default()
	return (decide(nil, false, false))
end

it("not listed reason: no drop", function()
	set_reasons("bad_behavior")
	local_ban("manual", 2)
	assert(d() == nil)
end)

it("default settings: nothing is read, nothing is written", function()
	local_ban("crowdsec", 4)
	assert(d() == nil)
	assert(seen_ip == nil, "no ban lookup with an empty setting")
	assert(next(ngx.shared.bans_meta._data) == nil, "bans_meta untouched")
end)

it("listed reason, Redis off, local ban: drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	local verdict, id, seen = decide(service, false, false)
	assert(verdict == "drop", tostring(verdict))
	assert(id == "crowdsec" and seen == ip)
end)

it("listed reason, no ban: no drop", function()
	set_reasons("crowdsec")
	assert(d() == nil)
end)

it("effective reason wins: service manual + global crowdsec lease", function()
	set_reasons("crowdsec")
	local_ban("manual", 1)
	assert(d() == nil)
end)

it("Redis on, no marker: no drop", function()
	vars.USE_REDIS = "yes"
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	assert(d() == nil)
end)

it("Redis on, valid marker: drop; stale marker epoch: no drop", function()
	vars.USE_REDIS = "yes"
	set_reasons("crowdsec")
	marker("crowdsec", 4, banlease.marker_epoch(ip, true))
	assert(d() == "drop")
	banlease.bump_marker_epoch(ip)
	assert(d() == nil)
end)

it("Redis on, marker whose epoch vanished: no drop, never creates an epoch", function()
	vars.USE_REDIS = "yes"
	set_reasons("crowdsec")
	marker("crowdsec", 4, banlease.marker_epoch(ip, true))
	assert(d() == "drop", "positive control")
	ngx.shared.bans_meta:delete("me_" .. ip)
	assert(d() == nil)
	assert(banlease.marker_epoch(ip, false) == nil, "the ClientHello path never creates an epoch")
end)

it("Redis on, valid marker and no local ban: the marker alone drops", function()
	vars.USE_REDIS = "yes"
	set_reasons("crowdsec")
	marker("crowdsec", 3, banlease.marker_epoch(ip, true))
	assert(d() == "drop")
end)

it("Redis on, marker for another service does not apply", function()
	vars.USE_REDIS = "yes"
	set_reasons("crowdsec")
	marker("crowdsec", 4, banlease.marker_epoch(ip, true), "other.example.com")
	assert(d() == nil)
end)

it("local hit overrides a marker only with a better rank", function()
	vars.USE_REDIS = "yes"
	set_reasons("crowdsec")
	marker("crowdsec", 4, banlease.marker_epoch(ip, true))
	local_ban("manual", 2)
	assert(d() == nil)
	local_ban("manual", 4)
	assert(d() == "drop", "an equal rank keeps the marker")
	local_ban("manual", 5)
	assert(d() == "drop", "a worse rank keeps the marker")
end)

it("proxy protocol or real ip: skip", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	assert(decide(service, false, false) == "drop", "positive control")
	assert(decide(service, true, false) == nil and decide(service, false, true) == nil)
end)

-- PROXY protocol behind a trusted proxy: the peer is 1.2.3.4, the client 9.9.9.9
local function behind_proxy(trusted)
	return decide(service, true, true, trusted)
end

it("proxy protocol, trusted peer: the PROXY address is banned, the peer address is not", function()
	set_reasons("crowdsec")
	pp_addr = "9.9.9.9"
	bans["9.9.9.9"] = { reason = "crowdsec", rank = 4 }
	local verdict, id, seen = behind_proxy("1.2.3.0/24")
	assert(verdict == "drop" and id == "crowdsec" and seen == "9.9.9.9", tostring(verdict) .. " " .. tostring(seen))
	assert(wl_args.ip == "9.9.9.9", "the whitelist is checked against the client")
	bans["9.9.9.9"] = nil
	local_ban("crowdsec", 4)
	assert(behind_proxy("1.2.3.0/24") == nil, "the proxy itself is not the client")
end)

it("proxy protocol, untrusted peer: falls back to the peer address", function()
	set_reasons("crowdsec")
	pp_addr = "9.9.9.9"
	bans["9.9.9.9"] = { reason = "crowdsec", rank = 4 }
	assert(behind_proxy("10.0.0.0/8") == nil, "a forged header bans nobody")
	local_ban("crowdsec", 4)
	local verdict, _, seen = behind_proxy("10.0.0.0/8")
	assert(verdict == "drop" and seen == ip)
	assert(behind_proxy("") == "drop", "an empty trusted list trusts nobody")
end)

it("proxy protocol, no header on the connection: the peer address", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	local verdict, _, seen = behind_proxy("1.2.3.0/24")
	assert(verdict == "drop" and seen == ip)
end)

it("proxy protocol: a lookup error or an unparsable address: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	pp_error = true
	assert(behind_proxy("1.2.3.0/24") == nil)
	pp_error, pp_addr = nil, "not an ip"
	assert(behind_proxy("1.2.3.0/24") == nil)
	pp_addr = nil
	assert(behind_proxy("1.2.3.0/24") == "drop", "positive control")
end)

it("proxy protocol: an IPv6 client is printed the way nginx prints $remote_addr", function()
	set_reasons("crowdsec")
	pp_addr = "2001:DB8::1"
	bans["2001:db8::1"] = { reason = "crowdsec", rank = 4 }
	local verdict, _, seen = behind_proxy("1.2.3.4")
	assert(verdict == "drop" and seen == "2001:db8::1", tostring(seen))
end)

-- The PROXY address must come out byte for byte as nginx's ngx_inet6_ntop prints $remote_addr (a mapped address stays
-- IPv6 there), or the ban and whitelist lookups of the ClientHello drop use a different key than the access phase
local function proxy_key(text)
	set_reasons("crowdsec")
	pp_addr, seen_ip = text, nil
	behind_proxy("1.2.3.4")
	return seen_ip
end

it("proxy protocol: IPv4-mapped address keeps its IPv6 spelling", function()
	for _, text in ipairs({ "::ffff:9.9.9.9", "::ffff:0909:0909", "::FFFF:9.9.9.9", "0:0:0:0:0:ffff:9.9.9.9" }) do
		assert(proxy_key(text) == "::ffff:9.9.9.9", text .. " -> " .. tostring(proxy_key(text)))
	end
	bans["::ffff:9.9.9.9"] = { reason = "crowdsec", rank = 4 }
	assert(behind_proxy("1.2.3.4") == "drop", "the ban keyed on nginx's $remote_addr is found")
	wl = true
	assert(behind_proxy("1.2.3.4") == nil, "a whitelist entry for the IPv6 spelling lifts the drop")
	assert(wl_args.ip == "::ffff:9.9.9.9", tostring(wl_args.ip))
end)

it("proxy protocol: leading zeros in an embedded IPv4 tail are read the way ngx_inet6_addr reads them", function()
	for _, text in ipairs({ "::ffff:009.009.009.009", "::ffff:9.9.9.009", "0:0:0:0:0:ffff:09.9.9.9", "::ffff:9..9.9" }) do
		local want = text == "::ffff:9..9.9" and "::ffff:9.0.9.9" or "::ffff:9.9.9.9"
		assert(proxy_key(text) == want, text .. " -> " .. tostring(proxy_key(text)))
	end
	for _, text in ipairs({
		"::ffff:255.255.255.255",
		"::ffff:1.2.3",
		"::ffff:1.2.3.4.5",
		"::ffff:256.1.1.1",
		"::ffff:00009.9.9.9",
		"::1.2:3",
	}) do
		local got = proxy_key(text)
		assert(got == nil, text .. " -> " .. tostring(got))
	end
end)

it("proxy protocol: IPv4-compatible and other dotted-tail addresses follow ngx_inet6_ntop", function()
	assert(proxy_key("::9.9.9.9") == "::9.9.9.9", tostring(proxy_key("::9.9.9.9")))
	assert(proxy_key("::0909:0909") == "::9.9.9.9")
	assert(proxy_key("::1.2.3.4") == "::1.2.3.4")
	assert(proxy_key("::ffff:0:1") == "::ffff:0.0.0.1")
	assert(proxy_key("::1") == "::1")
	assert(proxy_key("::2") == "::2")
	assert(proxy_key("::") == "::")
end)

it("proxy protocol: compression and case follow ngx_inet6_ntop", function()
	local cases = {
		["2001:DB8::1"] = "2001:db8::1",
		["2001:0db8:0000:0000:0000:0000:0000:0001"] = "2001:db8::1",
		["1::"] = "1::",
		["1:0:0:1::"] = "1:0:0:1::",
		["2001:db8:0:0:1:0:0:1"] = "2001:db8::1:0:0:1",
		["2001:db8:0:1:0:0:0:1"] = "2001:db8:0:1::1",
		["2001:db8:0:1:0:1:1:1"] = "2001:db8:0:1:0:1:1:1",
		["1:2:3:4:5:6:7:8"] = "1:2:3:4:5:6:7:8",
		["64:ff9b::1.2.3.4"] = "64:ff9b::102:304",
	}
	for text, want in pairs(cases) do
		local got = proxy_key(text)
		assert(got == want, text .. " -> " .. tostring(got) .. ", want " .. want)
	end
end)

it("proxy protocol: IPv4 text is read the way ngx_inet_addr reads it", function()
	assert(proxy_key("009.009.009.009") == "9.9.9.9", tostring(proxy_key("009.009.009.009")))
	assert(proxy_key("9.9.9.9") == "9.9.9.9")
	assert(proxy_key("255.255.255.255") == nil, "INADDR_NONE is no address for nginx")
	assert(proxy_key("1.2.3") == nil and proxy_key("256.1.1.1") == nil and proxy_key("[::1]") == nil)
end)

it("QUIC ClientHello: skip", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	assert(d() == "drop", "positive control")
	quic = true
	assert(d() == nil)
end)

it("extension lookup error: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	ext_error = true
	assert(d() == nil)
end)

it("default server keeps the per-service whitelist rescue", function()
	set_reasons("manual")
	local_ban("manual", 2)
	assert(d_default() == "drop", "positive control")
	wl_service_only = true
	assert(d_default() == nil)
	assert(wl_args.service == nil and wl_args.opts.local_only == true, "default server, local only")
end)

it("whitelisted: no drop; whitelist error: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	assert(d() == "drop", "positive control")
	wl = true
	assert(d() == nil)
	assert(wl_args.ip == ip and wl_args.service == service and wl_args.opts.local_only == true)
	ngx.shared.bans_meta:delete("wl_" .. service .. "_" .. ip)
	wl = "error"
	assert(d() == nil)
	assert(ngx.shared.bans_meta:get("wl_" .. service .. "_" .. ip) == nil, "an error leaves no memo")
	wl = false
	assert(d() == "drop", "the error left no memo that would hide the ban")
end)

it("a positive whitelist result is memoized for 10 s, a negative one never", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	wl = true
	assert(d() == nil)
	assert(ngx.shared.bans_meta.last_ttl["wl_" .. service .. "_" .. ip] == 10)
	wl = false
	assert(d() == nil, "memoized")
	ngx.shared.bans_meta:delete("wl_" .. service .. "_" .. ip)
	assert(d() == "drop")
	assert(ngx.shared.bans_meta:get("wl_" .. service .. "_" .. ip) == nil, "a negative result leaves no memo")
end)

it("detect mode: detect, never drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	vars.SECURITY_MODE = "detect"
	assert(d() == "detect")
end)

it("IPv4-mapped client keeps the IPv6 spelling nginx prints for $remote_addr", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	raw = string.rep("\0", 10) .. "\255\255\1\2\3\4"
	fam = "inet6"
	assert(d() == nil, "the IPv4 ban is not the key nginx looks up for this peer")
	assert(seen_ip == "::ffff:1.2.3.4", tostring(seen_ip))
end)

it("unsupported address: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	fam = "unix"
	assert(d() == nil)
	raw = nil
	assert(d() == nil)
end)

it("unreadable settings: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	assert(d() == "drop", "positive control")
	for _, name in ipairs({ "BANS_TLS_DROP_REASONS", "USE_REDIS", "SECURITY_MODE" }) do
		var_error = name
		assert(d() == nil, name)
	end
	var_error = nil
	vars.USE_REDIS = nil
	assert(d() == nil, "missing USE_REDIS")
end)

it("unknown reasons never match, even when the setting holds the same words", function()
	set_reasons("manual crowdsec")
	local_ban("manual crowdsec", 2)
	assert(d() == nil)
	vars.USE_REDIS = "yes"
	marker("crowdsec", 4, banlease.marker_epoch(ip, true))
	assert(d() == nil, "canonical lease marker beneath an unknown explicit reason")
end)

it("a listed word inside a longer reason name does not match", function()
	set_reasons("bad_behavior")
	local_ban("bad", 2)
	assert(d() == nil)
	set_reasons("crowdsec_extra")
	local_ban("crowdsec", 2)
	assert(d() == nil)
end)

it("any error: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	assert(d() == "drop", "positive control")
	utils_stub.is_banned_local = function()
		error("boom")
	end
	assert(d() == nil)
end)

it("a ban lookup that reports an error: no drop", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	utils_stub.is_banned_local = function()
		return nil, "datastore:get() error: boom", nil
	end
	assert(d() == nil)
end)

it("hook drops: ngx.exit(ngx.ERROR), counts the drop, warns once a minute per IP", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	worker_id = 3
	assert(banlease.tls_drop_hook(service, false, false) == true)
	assert(#exited == 1 and exited[1] == ngx.ERROR)
	assert(ngx.shared.metrics_datastore:get("tls_drops_crowdsec_3") == 1)
	assert(
		#logs == 1 and logs[1].level == ngx.WARN and logs[1].msg:find("dropped banned IP 1.2.3.4 (crowdsec)", 1, true)
	)
	assert(ngx.shared.bans_meta.last_ttl["tw_" .. ip] == 60)
	assert(banlease.tls_drop_hook(service, false, false) == true)
	assert(#exited == 2 and #logs == 1, "second drop: no second warning")
	assert(ngx.shared.metrics_datastore:get("tls_drops_crowdsec_3") == 2)
	worker_id = 0
end)

it("hook in detect mode: warns, never exits, counts nothing", function()
	set_reasons("crowdsec")
	local_ban("crowdsec", 4)
	vars.SECURITY_MODE = "detect"
	assert(banlease.tls_drop_hook(service, false, false) == nil)
	assert(#exited == 0)
	assert(#logs == 1 and logs[1].msg:find("detect mode: would drop banned IP 1.2.3.4 (crowdsec)", 1, true))
	assert(next(ngx.shared.metrics_datastore._data) == nil)
end)

it("hook without a verdict does nothing", function()
	set_reasons("crowdsec")
	assert(banlease.tls_drop_hook(service, false, false) == nil)
	assert(#exited == 0 and #logs == 0 and next(ngx.shared.metrics_datastore._data) == nil)
end)

if failures > 0 then
	print(failures .. " test(s) failed")
	os.exit(1)
end
