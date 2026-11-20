-- One identity per client address. NGINX prints $remote_addr in RFC 5952 form (lowercase, compressed), while an
-- operator, the API, the UI, the CLI or a feed may spell the same IPv6 address expanded or in upper case, and an
-- IPv4-mapped IPv6 address (::ffff:a.b.c.d) is the IPv4 address a.b.c.d (user decision, rc3). Pure Lua on purpose:
-- no ffi, so it runs under plain `lua` in the unit tests and costs no C call on the request path.
local byte = string.byte
local concat = table.concat
local find = string.find
local format = string.format
local match = string.match
local sub = string.sub
local floor = math.floor
local tonumber = tonumber

local ipaddr = {}

-- "a.b.c.d" with four decimal octets, no leading zero ("01" is ambiguous, inet_pton refuses it too)
local function parse_ipv4(text)
	local a, b, c, d = match(text, "^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
	if not a then
		return nil
	end
	local octets = { a, b, c, d }
	for i = 1, 4 do
		local s = octets[i]
		local n = tonumber(s)
		if #s > 3 or n > 255 or (#s > 1 and byte(s, 1) == 48) then
			return nil
		end
		octets[i] = n
	end
	return octets
end
ipaddr.parse_ipv4 = parse_ipv4

-- Eight 16-bit groups, or nil. No brackets, no zone id ("%eth0"), no prefix length.
local function parse_ipv6(text)
	if find(text, "[^%x:.]") or not find(text, ":", 1, true) then
		return nil
	end
	-- an IPv4 tail takes the place of the last two groups
	local head, tail = match(text, "^(.*:)(%d+%.%d+%.%d+%.%d+)$")
	if head then
		local v4 = parse_ipv4(tail)
		if not v4 then
			return nil
		end
		text = head .. format("%x:%x", v4[1] * 256 + v4[2], v4[3] * 256 + v4[4])
	elseif find(text, ".", 1, true) then
		return nil
	end
	local groups = {}
	local function read(part)
		local list = {}
		if part == "" then
			return list
		end
		for group in (part .. ":"):gmatch("([^:]*):") do
			if #group < 1 or #group > 4 then
				return nil
			end
			list[#list + 1] = tonumber(group, 16)
		end
		return list
	end
	local gap_start, gap_end = find(text, "::", 1, true)
	if gap_start then
		if find(text, "::", gap_end, true) or find(text, ":::", 1, true) then
			return nil
		end
		local left, right = read(sub(text, 1, gap_start - 1)), read(sub(text, gap_end + 1))
		if not left or not right or #left + #right > 7 then
			return nil
		end
		for i = 1, #left do
			groups[i] = left[i]
		end
		for i = #left + 1, 8 - #right do
			groups[i] = 0
		end
		for i = 1, #right do
			groups[8 - #right + i] = right[i]
		end
	else
		groups = read(text)
		if not groups or #groups ~= 8 then
			return nil
		end
	end
	return groups
end
ipaddr.parse_ipv6 = parse_ipv6

local function is_mapped(groups)
	for i = 1, 5 do
		if groups[i] ~= 0 then
			return false
		end
	end
	return groups[6] == 0xffff
end

-- RFC 5952: lowercase, no leading zeros, the first longest run of two or more zero groups becomes "::"
local function format_ipv6(groups)
	local best_start, best_len, run_start, run_len = 0, 0, 0, 0
	for i = 1, 8 do
		if groups[i] == 0 then
			if run_len == 0 then
				run_start = i
			end
			run_len = run_len + 1
			if run_len > best_len then
				best_start, best_len = run_start, run_len
			end
		else
			run_len = 0
		end
	end
	if best_len < 2 then
		best_start, best_len = 0, 0
	end
	-- Same dotted tail as ngx_inet6_ntop, so a client address spelled by NGINX normalizes to itself
	local last = 8
	local dotted
	if
		best_start == 1 and (best_len == 6 or (best_len == 7 and floor(groups[8] / 256) ~= 0 and groups[8] % 256 ~= 1))
	then
		last = 6
		dotted = format("%d.%d.%d.%d", floor(groups[7] / 256), groups[7] % 256, floor(groups[8] / 256), groups[8] % 256)
	end
	local out = {}
	local i = 1
	while i <= last do
		if i == best_start then
			out[#out + 1] = i == 1 and "::" or ":"
			i = i + best_len
		else
			out[#out + 1] = format("%x", groups[i])
			if i < last then
				out[#out + 1] = ":"
			end
			i = i + 1
		end
	end
	if dotted then
		out[#out + 1] = dotted
	end
	return concat(out)
end

-- Canonical text of an IP address, or nil when `text` is not a bare IPv4 / IPv6 address (brackets, zone id and
-- prefix length are refused). An IPv4-mapped address comes back as plain IPv4.
function ipaddr.normalize(text)
	if type(text) ~= "string" then
		return nil
	end
	local v4 = parse_ipv4(text)
	if v4 then
		return format("%d.%d.%d.%d", v4[1], v4[2], v4[3], v4[4])
	end
	local groups = parse_ipv6(text)
	if not groups then
		return nil
	end
	if is_mapped(groups) then
		return format("%d.%d.%d.%d", floor(groups[7] / 256), groups[7] % 256, floor(groups[8] / 256), groups[8] % 256)
	end
	return format_ipv6(groups)
end

-- Identity used inside storage keys. IPv4 text is already canonical when it comes from NGINX, so it skips the
-- parser; anything that is not an address is returned untouched (callers validate where it matters). IPv6 answers
-- are memoized per worker, bounded so a scan of many sources cannot grow it.
local KEY_CACHE_MAX = 2048
local key_cache, key_cache_size = {}, 0

function ipaddr.key(ip)
	if type(ip) ~= "string" or not find(ip, ":", 1, true) then
		return ip
	end
	local cached = key_cache[ip]
	if cached then
		return cached
	end
	cached = ipaddr.normalize(ip) or ip
	if key_cache_size >= KEY_CACHE_MAX then
		key_cache, key_cache_size = {}, 0
	end
	key_cache[ip] = cached
	key_cache_size = key_cache_size + 1
	return cached
end

return ipaddr
