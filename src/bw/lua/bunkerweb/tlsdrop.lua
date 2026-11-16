local clogger = require "bunkerweb.logger"
local ip_key = require("bunkerweb.ipaddr").key
local utils = require "bunkerweb.utils"

local logger = clogger:new("TLS-DROP")

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local byte = string.byte
local char = string.char
local concat = table.concat
local floor = math.floor
local format = string.format

local tlsdrop = {}

-- Ban reason as stored -> id used in BANS_TLS_DROP_REASONS. A ban created from a UI report keeps the
-- report's own reason and a CLI ban takes free text, so only these five can be listed.
local REASON_IDS = {
	["crowdsec"] = "crowdsec",
	["bad behavior"] = "bad_behavior",
	["manual"] = "manual",
	["ui"] = "ui",
	["api"] = "api",
}

function tlsdrop.reason_id(reason)
	return REASON_IDS[reason]
end

-- Port of ngx_inet6_ntop: the text nginx prints for an IPv6 $remote_addr. It compresses the first longest run of
-- two or more zero words and writes the last 32 bits in dotted form for ::a.b.c.d and ::ffff:a.b.c.d.
local function inet6_ntop(packed)
	local p = { byte(packed, 1, 16) }
	local zero, last, max, n = -1, -1, 1, 0
	for i = 0, 14, 2 do
		if p[i + 1] ~= 0 or p[i + 2] ~= 0 then
			if max < n then
				zero, max = last, n
			end
			n = 0
		else
			if n == 0 then
				last = i
			end
			n = n + 1
		end
	end
	if max < n then
		zero, max = last, n
	end
	local parts, count = {}, 0
	n = 16
	if zero == 0 then
		if (max == 5 and p[11] == 0xff and p[12] == 0xff) or max == 6 or (max == 7 and p[15] ~= 0 and p[16] ~= 1) then
			n = 12
		end
		count = count + 1
		parts[count] = ":"
	end
	local i = 0
	while i < n do
		if i == zero then
			count = count + 1
			parts[count] = ":"
			i = i + max * 2
		else
			count = count + 1
			parts[count] = format("%x", p[i + 1] * 256 + p[i + 2])
			if i < 14 then
				count = count + 1
				parts[count] = ":"
			end
			i = i + 2
		end
	end
	if n == 12 then
		count = count + 1
		parts[count] = format("%d.%d.%d.%d", p[13], p[14], p[15], p[16])
	end
	return concat(parts)
end
tlsdrop.inet6_ntop = inet6_ntop

-- Text of the peer address of the connection, as nginx prints it for $remote_addr.
function tlsdrop.format_raw_addr(packed, family)
	if type(packed) ~= "string" then
		return nil, "no address"
	end
	if family == "inet" and #packed == 4 then
		return format("%d.%d.%d.%d", byte(packed, 1, 4))
	end
	if family ~= "inet6" or #packed ~= 16 then
		return nil, "unsupported address family"
	end
	-- nginx prints an IPv4-mapped peer of a dual-stack listener as ::ffff:a.b.c.d, but every ban key names that client
	-- by its IPv4 address (bunkerweb.ipaddr), so the ClientHello judges the same identity as the HTTP phases.
	return ip_key(inet6_ntop(packed))
end

-- Port of ngx_inet_addr, which ngx_parse_addr tries before IPv6: unlike inet_pton it takes leading zeros and
-- empty octets, and it refuses 255.255.255.255 because that value is INADDR_NONE.
local function inet_addr(text)
	local addr, octet, dots = 0, 0, 0
	for i = 1, #text do
		local c = byte(text, i)
		if c >= 48 and c <= 57 then
			octet = octet * 10 + c - 48
			if octet > 255 then
				return nil
			end
		elseif c == 46 and dots < 3 then
			addr = addr * 256 + octet
			octet = 0
			dots = dots + 1
		else
			return nil
		end
	end
	if dots ~= 3 then
		return nil
	end
	addr = addr * 256 + octet
	if addr == 4294967295 then
		return nil
	end
	return format("%d.%d.%d.%d", floor(addr / 16777216), floor(addr / 65536) % 256, floor(addr / 256) % 256, addr % 256)
end
tlsdrop.inet_addr = inet_addr

-- The PROXY source address spelled exactly as nginx's realip module leaves it in $remote_addr, which every ban and
-- whitelist key uses: ngx_parse_addr, then ngx_sock_ntop. An IPv4-mapped address is then its IPv4 address (ipaddr.key).
function tlsdrop.canonical_addr(text)
	local v4 = inet_addr(text)
	if v4 then
		return v4
	end
	if text:find("[", 1, true) then
		return nil -- resty.ipmatcher strips brackets, nginx does not
	end
	-- ngx_inet6_addr reads an embedded IPv4 tail with ngx_inet_addr (leading zeros, empty octets), inet_pton does not
	local head, tail = text:match("^(.*:)(%d%d?%d?%d?%.[%d%.]*)$")
	if head then
		tail = inet_addr(tail)
		if not tail then
			return nil
		end
		text = head .. tail
	end
	local v6 = require("resty.ipmatcher").parse_ipv6(text)
	if not v6 then
		return nil
	end
	local bytes = {}
	for i = 1, 4 do
		local n = v6[i]
		bytes[#bytes + 1] = char(floor(n / 16777216) % 256, floor(n / 65536) % 256, floor(n / 256) % 256, n % 256)
	end
	return ip_key(inet6_ntop(concat(bytes)))
end

local trusted_matchers = {}

-- Client IP of a connection that came in with a PROXY protocol header. nginx's realip module swaps it in for
-- $remote_addr only when the peer is listed in set_real_ip_from, so do the same: "trusted" is that list, as the
-- template rendered it. Returns the peer address when there is no header or the peer is not trusted, and nil
-- ("do not drop") whenever the answer is not certain.
function tlsdrop.proxy_protocol_client_ip(peer, trusted)
	if not peer then
		return nil
	end
	local text, err = require("ngx.ssl").proxy_protocol_addr()
	if err then
		return nil
	end
	if not text then
		return peer
	end
	local matcher = trusted_matchers[trusted]
	if not matcher then
		local networks = {}
		for network in trusted:gmatch("%S+") do
			networks[#networks + 1] = network
		end
		if #networks == 0 then
			return peer
		end
		matcher = require("resty.ipmatcher").new(networks)
		if not matcher then
			return nil
		end
		trusted_matchers[trusted] = matcher
	end
	local is_trusted, match_err = matcher:match(peer)
	if match_err then
		return nil
	end
	if not is_trusted then
		return peer
	end
	return tlsdrop.canonical_addr(text)
end

-- ClientHello drop. Nothing below may yield: no Redis, no cosocket, no mlcache callback, no resty.lock, no sleep, no
-- ngx.var. Every unknown means "do not drop": the access phase stays authoritative.
-- Returns "drop" | "detect" | nil, the canonical reason id and the client IP.
-- "trusted" is only set when real IP is configured for the PROXY protocol: the networks allowed to send the header.
-- Otherwise a PROXY protocol or header based real IP means the client IP is unknown here: skip.
local function decide(service, proxy_protocol, real_ip, trusted)
	if not trusted and (proxy_protocol or real_ip) then
		return nil
	end
	local ctx = service and { bw = { server_name = service } } or nil
	local reasons = utils.get_variable("BANS_TLS_DROP_REASONS", service ~= nil, ctx)
	if reasons == nil or reasons == "" then
		return nil -- off, or unreadable: fail open
	end
	local security_mode = utils.get_variable("SECURITY_MODE", service ~= nil, ctx)
	if security_mode == nil then
		return nil
	end
	-- QUIC transport parameters: never dropped here, the access phase enforces the ban
	local quic, quic_err = require("ngx.ssl.clienthello").get_client_hello_ext(57)
	if quic or quic_err then
		return nil
	end
	local ip = tlsdrop.format_raw_addr(require("ngx.ssl").raw_client_addr())
	if trusted then
		ip = tlsdrop.proxy_protocol_client_ip(ip, trusted)
	end
	if not ip then
		return nil
	end
	-- A local hit is authoritative for the access phase too (is_banned asks Redis only when every scope
	-- missed locally), so it is the verdict here as well. A miss, with Redis or not, is never a drop.
	local banned, reason = utils.is_banned_local(ip, service)
	if not banned then
		return nil
	end
	local id = REASON_IDS[reason]
	if not id or not (" " .. reasons .. " "):find(" " .. id .. " ", 1, true) then
		return nil
	end
	local whitelisted = utils.is_ip_whitelisted(ip, service, { local_only = true })
	if whitelisted ~= false then
		return nil -- whitelisted or unknown: the access phase decides
	end
	if security_mode == "detect" then
		return "detect", id, ip
	end
	return "drop", id, ip
end

function tlsdrop.decide(service, proxy_protocol, real_ip, trusted)
	local ok, verdict, id, ip = pcall(decide, service, proxy_protocol, real_ip, trusted)
	if not ok then
		return nil
	end
	return verdict, id, ip
end

-- One warning per IP and minute per worker, in a table that cannot grow past WARN_MAX_IPS: a flood of
-- distinct banned addresses must not turn the log into a memory leak or a log flood.
local WARN_INTERVAL = 60
local WARN_MAX_IPS = 1024
local warned, warned_count = {}, 0

local function should_warn(ip)
	local now = ngx.time()
	local expires = warned[ip]
	if expires and expires > now then
		return false
	end
	if not expires then
		if warned_count >= WARN_MAX_IPS then
			for key, until_time in pairs(warned) do
				if until_time <= now then
					warned[key] = nil
					warned_count = warned_count - 1
				end
			end
			if warned_count >= WARN_MAX_IPS then
				warned, warned_count = {}, 0
			end
		end
		warned_count = warned_count + 1
	end
	warned[ip] = now + WARN_INTERVAL
	return true
end

-- Plugins that export a module-level client_hello(hello), in PLUGINS_ORDER_SSL_CLIENT_HELLO order. Built once per
-- worker, on its first handshake: nothing is required, built or looked up per handshake after that.
tlsdrop.CLIENT_HELLO_PLUGIN_HOOK = 1 -- capability flag, the way plugins detect the hook
local hello_plugins, hello_plugin_ids = {}, {}
local hello_registered = false

-- Keeps the plugins of the order whose main module exports a client_hello function and returns their ids.
function tlsdrop.register_client_hello_plugins(plugin_ids)
	local list, ids, registered = {}, {}, {}
	for _, id in ipairs(plugin_ids or {}) do
		if not ids[id] then
			local ok, module = pcall(require, id .. "/" .. id)
			if ok and type(module) == "table" and type(module.client_hello) == "function" then
				list[#list + 1] = { id = id, fn = module.client_hello }
				ids[id] = true
				registered[#registered + 1] = id
			elseif not ok and not tostring(module):find("not found", 1, true) then
				logger:log(WARN, "can't load plugin " .. id .. " for the ClientHello hook : " .. tostring(module))
			end
		end
	end
	hello_plugins, hello_plugin_ids = list, ids
	return registered
end

-- True when the plugin is called through client_hello(): the default server's legacy loop skips it.
function tlsdrop.is_client_hello_plugin(id)
	return hello_plugin_ids[id] == true
end

-- A worker that starts while the order is not published yet (loading) tries again on its next handshake.
local function ensure_registered()
	if hello_registered then
		return
	end
	local order = require("bunkerweb.datastore"):new(ngx.shared.internalstore):get("plugins_order", true)
	if not order then
		return
	end
	hello_registered = true
	if type(order.ssl_client_hello) == "table" and #order.ssl_client_hello > 0 then
		local registered = tlsdrop.register_client_hello_plugins(order.ssl_client_hello)
		if #registered > 0 then
			logger:log(ngx.INFO, "plugins called at the TLS ClientHello : " .. concat(registered, " "))
		end
	end
end

local function plain_reason(reason)
	if type(reason) ~= "string" then
		return ""
	end
	return (reason:sub(1, 256):gsub("%c", " "))
end

-- Nothing below may yield either (same rule as decide): ngx.ssl and the plugins' own functions. Any error, or any
-- verdict but "drop" and "detect", means "do not drop". Returns true when a plugin dropped the handshake.
local function run_client_hello_plugins(service, proxy_protocol, real_ip, trusted)
	local packed, family = require("ngx.ssl").raw_client_addr()
	if not packed then
		return false
	end
	local quic, quic_err = require("ngx.ssl.clienthello").get_client_hello_ext(57)
	if quic_err then
		return false
	end
	-- Behind a PROXY protocol header or a header based real IP the peer is not the client, unless its networks are
	-- trusted and nginx's own rule picks the PROXY address
	local ip
	if trusted or not (proxy_protocol or real_ip) then
		ip = tlsdrop.format_raw_addr(packed, family)
		if ip and trusted then
			ip = tlsdrop.proxy_protocol_client_ip(ip, trusted)
		end
	end
	local hello = {
		service = service,
		ip = ip,
		raw = packed,
		family = family,
		quic = quic and true or false,
		proxy_protocol = proxy_protocol and true or false,
		real_ip = real_ip and true or false,
		trusted = trusted,
	}
	local who = ip or "an unknown address"
	for _, plugin in ipairs(hello_plugins) do
		local ok, verdict, reason = pcall(plugin.fn, hello)
		if not ok then
			if should_warn("error_" .. plugin.id) then
				logger:log(ERR, "plugin " .. plugin.id .. " client_hello() failed : " .. tostring(verdict))
			end
		elseif verdict == "detect" then
			if should_warn("detect_" .. plugin.id .. "_" .. who) then
				logger:log(
					WARN,
					"detect mode: plugin "
						.. plugin.id
						.. " would drop "
						.. who
						.. " at the TLS ClientHello : "
						.. plain_reason(reason)
				)
			end
		elseif verdict == "drop" then
			if should_warn("drop_" .. plugin.id .. "_" .. who) then
				logger:log(
					WARN,
					"plugin " .. plugin.id .. " dropped " .. who .. " at the TLS ClientHello : " .. plain_reason(reason)
				)
			end
			return true
		end
	end
	return false
end

-- Called from ssl_client_hello_by_lua. Returns true after closing the handshake, nothing otherwise.
function tlsdrop.hook(service, proxy_protocol, real_ip, trusted)
	local verdict, id, ip = tlsdrop.decide(service, proxy_protocol, real_ip, trusted)
	if verdict then
		local warn = should_warn(ip)
		if verdict == "detect" then
			if warn then
				logger:log(WARN, "detect mode: would drop banned IP " .. ip .. " (" .. id .. ") at the TLS ClientHello")
			end
		else
			if warn then
				logger:log(WARN, "dropped banned IP " .. ip .. " (" .. id .. ") at the TLS ClientHello")
			end
			ngx.exit(ngx.ERROR)
			return true
		end
	end
	-- Not dropped by the core, in both modes and whatever BANS_TLS_DROP_REASONS says: the plugins get their turn
	local registered, register_err = pcall(ensure_registered)
	if not registered and should_warn("register") then
		logger:log(ERR, "can't register the ClientHello plugins : " .. tostring(register_err))
	end
	if #hello_plugins == 0 then
		return
	end
	local ok, dropped = pcall(run_client_hello_plugins, service, proxy_protocol, real_ip, trusted)
	if ok and dropped then
		ngx.exit(ngx.ERROR)
		return true
	end
end

return tlsdrop
