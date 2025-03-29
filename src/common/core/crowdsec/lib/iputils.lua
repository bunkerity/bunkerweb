-- This code uses some functions from
-- https://github.com/libmoon/libmoon/blob/master/lua/utils.lua

local _M = {}
local bit = require 'crowdsec.lib.bitop'
local bor, band, rshift, lshift, bswap = bit.bor, bit.band, bit.rshift, bit.lshift, bit.bswap

--- Byte swap for 16 bit integers
--- @param n 16 bit integer
--- @return Byte swapped integer
function bswap16(n)
    return bor(rshift(n, 8), lshift(band(n, 0xFF), 8))
end

hton16 = bswap16
ntoh16 = hton16

_G.bswap = bswap -- export bit.bswap to global namespace to be consistent with bswap16
hton = bswap
ntoh = hton

local ffi = require "ffi"

local ipv4_netmasks = {
    4294967295, 4294967294, 4294967292, 4294967288, 4294967280, 4294967264, 4294967232, 4294967168, 4294967040, 4294966784,
    4294966272, 4294965248, 4294963200, 4294959104, 4294950912, 4294934528, 4294901760, 4294836224, 4294705152, 4294443008,
    4293918720, 4292870144, 4290772992, 4286578688, 4278190080, 4261412864, 4227858432, 4160749568, 4026531840, 3758096384, 3221225472, 2147483648, 0
}

local ipv6_netmasks = {
    {4294967295,4294967295,4294967295,4294967295}, {4294967295,4294967295,4294967295,4294967294}, {4294967295,4294967295,4294967295,4294967292},
    {4294967295,4294967295,4294967295,4294967288}, {4294967295,4294967295,4294967295,4294967280}, {4294967295,4294967295,4294967295,4294967264},
    {4294967295,4294967295,4294967295,4294967232}, {4294967295,4294967295,4294967295,4294967168}, {4294967295,4294967295,4294967295,4294967040},
    {4294967295,4294967295,4294967295,4294966784}, {4294967295,4294967295,4294967295,4294966272}, {4294967295,4294967295,4294967295,4294965248},
    {4294967295,4294967295,4294967295,4294963200}, {4294967295,4294967295,4294967295,4294959104}, {4294967295,4294967295,4294967295,4294950912},
    {4294967295,4294967295,4294967295,4294934528}, {4294967295,4294967295,4294967295,4294901760}, {4294967295,4294967295,4294967295,4294836224},
    {4294967295,4294967295,4294967295,4294705152}, {4294967295,4294967295,4294967295,4294443008}, {4294967295,4294967295,4294967295,4293918720},
    {4294967295,4294967295,4294967295,4292870144}, {4294967295,4294967295,4294967295,4290772992}, {4294967295,4294967295,4294967295,4286578688},
    {4294967295,4294967295,4294967295,4278190080}, {4294967295,4294967295,4294967295,4261412864}, {4294967295,4294967295,4294967295,4227858432},
    {4294967295,4294967295,4294967295,4160749568}, {4294967295,4294967295,4294967295,4026531840}, {4294967295,4294967295,4294967295,3758096384},
    {4294967295,4294967295,4294967295,3221225472}, {4294967295,4294967295,4294967295,2147483648}, {4294967295,4294967295,4294967295,0},
    {4294967295,4294967295,4294967294,0}, {4294967295,4294967295,4294967292,0}, {4294967295,4294967295,4294967288,0},
    {4294967295,4294967295,4294967280,0}, {4294967295,4294967295,4294967264,0}, {4294967295,4294967295,4294967232,0},
    {4294967295,4294967295,4294967168,0}, {4294967295,4294967295,4294967040,0}, {4294967295,4294967295,4294966784,0},
    {4294967295,4294967295,4294966272,0}, {4294967295,4294967295,4294965248,0}, {4294967295,4294967295,4294963200,0},
    {4294967295,4294967295,4294959104,0}, {4294967295,4294967295,4294950912,0}, {4294967295,4294967295,4294934528,0},
    {4294967295,4294967295,4294901760,0}, {4294967295,4294967295,4294836224,0}, {4294967295,4294967295,4294705152,0},
    {4294967295,4294967295,4294443008,0}, {4294967295,4294967295,4293918720,0}, {4294967295,4294967295,4292870144,0},
    {4294967295,4294967295,4290772992,0}, {4294967295,4294967295,4286578688,0}, {4294967295,4294967295,4278190080,0},
    {4294967295,4294967295,4261412864,0}, {4294967295,4294967295,4227858432,0}, {4294967295,4294967295,4160749568,0},
    {4294967295,4294967295,4026531840,0}, {4294967295,4294967295,3758096384,0}, {4294967295,4294967295,3221225472,0},
    {4294967295,4294967295,2147483648,0},
    {4294967295,4294967295,0,0}, {4294967295,4294967294,0,0}, {4294967295,4294967292,0,0}, {4294967295,4294967288,0,0},
    {4294967295,4294967280,0,0}, {4294967295,4294967264,0,0}, {4294967295,4294967232,0,0}, {4294967295,4294967168,0,0},
    {4294967295,4294967040,0,0}, {4294967295,4294966784,0,0}, {4294967295,4294966272,0,0}, {4294967295,4294965248,0,0},
    {4294967295,4294963200,0,0}, {4294967295,4294959104,0,0}, {4294967295,4294950912,0,0}, {4294967295,4294934528,0,0},
    {4294967295,4294901760,0,0}, {4294967295,4294836224,0,0}, {4294967295,4294705152,0,0}, {4294967295,4294443008,0,0},
    {4294967295,4293918720,0,0}, {4294967295,4292870144,0,0}, {4294967295,4290772992,0,0}, {4294967295,4286578688,0,0},
    {4294967295,4278190080,0,0}, {4294967295,4261412864,0,0}, {4294967295,4227858432,0,0}, {4294967295,4160749568,0,0},
    {4294967295,4026531840,0,0}, {4294967295,3758096384,0,0}, {4294967295,3221225472,0,0}, {4294967295,2147483648,0,0},
    {4294967295,0,0,0},{4294967294,0,0,0},{4294967292,0,0,0}, {4294967288,0,0,0}, {4294967280,0,0,0},{4294967264,0,0,0},
    {4294967232,0,0,0},{4294967168,0,0,0},{4294967040,0,0,0}, {4294966784,0,0,0},{4294966272,0,0,0},{4294965248,0,0,0},
    {4294963200,0,0,0},{4294959104,0,0,0},{4294950912,0,0,0}, {4294934528,0,0,0},{4294901760,0,0,0},{4294836224,0,0,0},
    {4294705152,0,0,0},{4294443008,0,0,0},{4293918720,0,0,0}, {4292870144,0,0,0},{4290772992,0,0,0},{4286578688,0,0,0},
    {4278190080,0,0,0},{4261412864,0,0,0},{4227858432,0,0,0}, {4160749568,0,0,0},{4026531840,0,0,0},{3758096384,0,0,0},
    {3221225472,0,0,0},{2147483648,0,0,0},{0,0,0,0}
}

local netmasks_by_key_type = {}
netmasks_by_key_type["ipv4"] = ipv4_netmasks
netmasks_by_key_type["ipv6"] = ipv6_netmasks

_M.netmasks_by_key_type = netmasks_by_key_type

function _M.ipToInt( str )
	local num = 0
	if str and type(str)=="string" then
		local o1,o2,o3,o4 = str:match("(%d+)%.(%d+)%.(%d+)%.(%d+)" )
		num = 2^24*o1 + 2^16*o2 + 2^8*o3 + o4
	end
    return num
end

function _M.concatIPv6(ip)
    if type(ip) == "table" and table.getn(ip) == 4 then
        return ip[1]*2^96 + ip[2]*2^64 + ip[3]*2^32 + ip[4]
    end
    return nil
end

function _M.ipv6_band(ip, netmask)
    local res_table = {}
    local nb = 1
    for item in ip.gmatch(ip, "([^:]+)") do
      table.insert(res_table, bit.band(tonumber(item), netmask[nb]))
      nb = nb + 1
    end
    return table.concat(res_table, ":")
end

function _M.ipv4_band(ip, netmask)
    return bit.band(ip, netmask)
end

function _M.splitRange(range)
    if range and type(range) == "string" then
        local ip_address, cidr = range:match("^([^/]+)/(%d+)")
        return ip_address, tonumber(cidr)
    end
    return nil, nil
end

function _M.cidrToInt(cidr, ip_version)
    if cidr and type(cidr) ~= "number" and ip_version and type(ip_version) ~= "string" then
        return nil
    end
    if ip_version == "ipv4" then
        return tostring(ipv4_netmasks[32-cidr+1])
    end
    if ip_version == "ipv6" then
        return table.concat(ipv6_netmasks[128-cidr+1], ":")
    end
end

--- Parse a string to an IP address
--- @return address ip address in ip4_address or ip6_address format or nil if invalid address
--- @return boolean true if IPv4 address, false otherwise
function _M.parseIPAddress(ip)
    ip = tostring(ip)
    local address = parseIP4Address(ip)
    if address == nil then
        return parseIP6Address(ip), false
    end
    return address, true
end

--- Parse a string to an IPv4 address
--- @param ip address in string format
--- @return address in uint32 format or nil if invalid address
function parseIP4Address(ip)
    ip = tostring(ip)
    local bytes = {string.match(ip, '(%d+)%.(%d+)%.(%d+)%.(%d+)')}
    if bytes == nil then
        return
    end
    for i = 1, 4 do
        if bytes[i] == nil then
            return
        end
        bytes[i] = tonumber(bytes[i])
        if  bytes[i] < 0 or bytes[i] > 255 then
            return
        end
    end

    -- build a uint32
    ip = bytes[1]
    for i = 2, 4 do
        ip = bor(lshift(ip, 8), bytes[i])
    end
    return ip
end

ffi.cdef[[
	union ip6_address {
		uint8_t 	uint8[16];
		uint32_t	uint32[4];
		uint64_t	uint64[2];
	};
]]

ffi.cdef[[
int inet_pton(int af, const char *src, void *dst);
]]

--- Parse a string to an IPv6 address
--- @param ip address in string format
--- @return address in ip6_address format or nil if invalid address
function parseIP6Address(ip)
    ip = tostring(ip)
    local LINUX_AF_INET6 = 10 --preprocessor constant of Linux
    local tmp_addr = ffi.new("union ip6_address")
    local res = ffi.C.inet_pton(LINUX_AF_INET6, ip, tmp_addr)
    if res == 0 then
        return nil
    end

    local addr = ffi.new("union ip6_address")
    addr.uint32[0] = bswap(tmp_addr.uint32[3])
    addr.uint32[1] = bswap(tmp_addr.uint32[2])
    addr.uint32[2] = bswap(tmp_addr.uint32[1])
    addr.uint32[3] = bswap(tmp_addr.uint32[0])

    return addr
end

--- Merge tables.
--- @param args Arbitrary amount of tables to get merged.
function mergeTables(...)
    local table = {}
    if select("#", ...) > 0 then
        table = select(1, ...)
        for i = 2, select("#", ...) do
            for k,v in pairs(select(i, ...)) do
                table[k] = v
            end
        end
    end
    return table
end

local band = bit.band
local sar = bit.arshift

return _M
