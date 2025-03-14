-- net/url.lua - a robust url parser and builder
--
-- Bertrand Mansion, 2011-2021; License MIT
-- @module net.url
-- @alias	M

local M = {}
M.version = "1.1.0"

--- url options
-- - `separator` is set to `&` by default but could be anything like `&amp;amp;` or `;`
-- - `cumulative_parameters` is false by default. If true, query parameters with the same name will be stored in a table.
-- - `legal_in_path` is a table of characters that will not be url encoded in path components
-- - `legal_in_query` is a table of characters that will not be url encoded in query values. Query parameters only support a small set of legal characters (-_.).
-- - `query_plus_is_space` is true by default, so a plus sign in a query value will be converted to %20 (space), not %2B (plus)
-- @todo Add option to limit the size of the argument table
-- @todo Add option to limit the depth of the argument table
-- @todo Add option to process dots in parameter names, ie. `param.filter=1`
M.options = {
	separator = '&',
	cumulative_parameters = false,
	legal_in_path = {
		[":"] = true, ["-"] = true, ["_"] = true, ["."] = true,
		["!"] = true, ["~"] = true, ["*"] = true, ["'"] = true,
		["("] = true, [")"] = true, ["@"] = true, ["&"] = true,
		["="] = true, ["$"] = true, [","] = true,
		[";"] = true
	},
	legal_in_query = {
		[":"] = true, ["-"] = true, ["_"] = true, ["."] = true,
		[","] = true, ["!"] = true, ["~"] = true, ["*"] = true,
		["'"] = true, [";"] = true, ["("] = true, [")"] = true,
		["@"] = true, ["$"] = true,
	},
	query_plus_is_space = true
}

--- list of known and common scheme ports
-- as documented in <a href="http://www.iana.org/assignments/uri-schemes.html">IANA URI scheme list</a>
M.services = {
	acap     = 674,
	cap      = 1026,
	dict     = 2628,
	ftp      = 21,
	gopher   = 70,
	http     = 80,
	https    = 443,
	iax      = 4569,
	icap     = 1344,
	imap     = 143,
	ipp      = 631,
	ldap     = 389,
	mtqp     = 1038,
	mupdate  = 3905,
	news     = 2009,
	nfs      = 2049,
	nntp     = 119,
	rtsp     = 554,
	sip      = 5060,
	snmp     = 161,
	telnet   = 23,
	tftp     = 69,
	vemmi    = 575,
	afs      = 1483,
	jms      = 5673,
	rsync    = 873,
	prospero = 191,
	videotex = 516
}

local function decode(str)
	return (str:gsub("%%(%x%x)", function(c)
		return string.char(tonumber(c, 16))
	end))
end

local function encode(str, legal)
	return (str:gsub("([^%w])", function(v)
		if legal[v] then
			return v
		end
		return string.upper(string.format("%%%02x", string.byte(v)))
	end))
end

-- for query values, + can mean space if configured as such
local function decodeValue(str)
	if M.options.query_plus_is_space then
		str = str:gsub('+', ' ')
	end
	return decode(str)
end

local function concat(a, b)
	if type(a) == 'table' then
		return a:build() .. b
	else
		return a .. b:build()
	end
end

function M:addSegment(path)
	if type(path) == 'string' then
		self.path = self.path .. '/' .. encode(path:gsub("^/+", ""), M.options.legal_in_path)
	end
	return self
end

--- builds the url
-- @return a string representing the built url
function M:build()
	local url = ''
	if self.path then
		local path = self.path
		url = url .. tostring(path)
	end
	if self.query then
		local qstring = tostring(self.query)
		if qstring ~= "" then
			url = url .. '?' .. qstring
		end
	end
	if self.host then
		local authority = self.host
		if self.port and self.scheme and M.services[self.scheme] ~= self.port then
			authority = authority .. ':' .. self.port
		end
		local userinfo
		if self.user and self.user ~= "" then
			userinfo = self.user
			if self.password then
				userinfo = userinfo .. ':' .. self.password
			end
		end
		if userinfo and userinfo ~= "" then
			authority = userinfo .. '@' .. authority
		end
		if authority then
			if url ~= "" then
				url = '//' .. authority .. '/' .. url:gsub('^/+', '')
			else
				url = '//' .. authority
			end
		end
	end
	if self.scheme then
		url = self.scheme .. ':' .. url
	end
	if self.fragment then
		url = url .. '#' .. self.fragment
	end
	return url
end

--- builds the querystring
-- @param tab The key/value parameters
-- @param sep The separator to use (optional)
-- @param key The parent key if the value is multi-dimensional (optional)
-- @return a string representing the built querystring
function M.buildQuery(tab, sep, key)
	local query = {}
	if not sep then
		sep = M.options.separator or '&'
	end
	local keys = {}
	for k in pairs(tab) do
		keys[#keys+1] = k
	end
	table.sort(keys, function (a, b)
  		local function padnum(n, rest) return ("%03d"..rest):format(tonumber(n)) end
  		return tostring(a):gsub("(%d+)(%.)",padnum) < tostring(b):gsub("(%d+)(%.)",padnum)
	end)
	for _,name in ipairs(keys) do
		local value = tab[name]
		name = encode(tostring(name), {["-"] = true, ["_"] = true, ["."] = true})
		if key then
			if M.options.cumulative_parameters and string.find(name, '^%d+$') then
				name = tostring(key)
			else
				name = string.format('%s[%s]', tostring(key), tostring(name))
			end
		end
		if type(value) == 'table' then
			query[#query+1] = M.buildQuery(value, sep, name)
		else
			local value = encode(tostring(value), M.options.legal_in_query)
			if value ~= "" then
				query[#query+1] = string.format('%s=%s', name, value)
			else
				query[#query+1] = name
			end
		end
	end
	return table.concat(query, sep)
end

--- Parses the querystring to a table
-- This function can parse multidimensional pairs and is mostly compatible
-- with PHP usage of brackets in key names like ?param[key]=value
-- @param str The querystring to parse
-- @param sep The separator between key/value pairs, defaults to `&`
-- @todo limit the max number of parameters with M.options.max_parameters
-- @return a table representing the query key/value pairs
function M.parseQuery(str, sep)
	if not sep then
		sep = M.options.separator or '&'
	end

	local values = {}
	for key,val in str:gmatch(string.format('([^%q=]+)(=*[^%q=]*)', sep, sep)) do
		local key = decodeValue(key)
		local keys = {}
		key = key:gsub('%[([^%]]*)%]', function(v)
				-- extract keys between balanced brackets
				if string.find(v, "^-?%d+$") then
					v = tonumber(v)
				else
					v = decodeValue(v)
				end
				table.insert(keys, v)
				return "="
		end)
		key = key:gsub('=+.*$', "")
		key = key:gsub('%s', "_") -- remove spaces in parameter name
		val = val:gsub('^=+', "")

		if not values[key] then
			values[key] = {}
		end
		if #keys > 0 and type(values[key]) ~= 'table' then
			values[key] = {}
		elseif #keys == 0 and type(values[key]) == 'table' then
			values[key] = decodeValue(val)
		elseif M.options.cumulative_parameters
			and type(values[key]) == 'string' then
			values[key] = { values[key] }
			table.insert(values[key], decodeValue(val))
		end

		local t = values[key]
		for i,k in ipairs(keys) do
			if type(t) ~= 'table' then
				t = {}
			end
			if k == "" then
				k = #t+1
			end
			if not t[k] then
				t[k] = {}
			end
			if i == #keys then
				t[k] = val
			end
			t = t[k]
		end

	end
	setmetatable(values, { __tostring = M.buildQuery })
	return values
end

--- set the url query
-- @param query Can be a string to parse or a table of key/value pairs
-- @return a table representing the query key/value pairs
function M:setQuery(query)
	local query = query
	if type(query) == 'table' then
		query = M.buildQuery(query)
	end
	self.query = M.parseQuery(query)
	return query
end

--- set the authority part of the url
-- The authority is parsed to find the user, password, port and host if available.
-- @param authority The string representing the authority
-- @return a string with what remains after the authority was parsed
function M:setAuthority(authority)
	self.authority = authority
	self.port = nil
	self.host = nil
	self.userinfo = nil
	self.user = nil
	self.password = nil

	authority = authority:gsub('^([^@]*)@', function(v)
		self.userinfo = v
		return ''
	end)

	authority = authority:gsub(':(%d+)$', function(v)
		self.port = tonumber(v)
		return ''
	end)

	local function getIP(str)
		-- ipv4
		local chunks = { str:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$") }
		if #chunks == 4 then
			for _, v in pairs(chunks) do
				if tonumber(v) > 255 then
					return false
				end
			end
			return str
		end
		-- ipv6
		local chunks = { str:match("^%["..(("([a-fA-F0-9]*):"):rep(8):gsub(":$","%%]$"))) }
		if #chunks == 8 or #chunks < 8 and
			str:match('::') and not str:gsub("::", "", 1):match('::') then
			for _,v in pairs(chunks) do
				if #v > 0 and tonumber(v, 16) > 65535 then
					return false
				end
			end
			return str
		end
		return nil
	end

	local ip = getIP(authority)
	if ip then
		self.host = ip
	elseif type(ip) == 'nil' then
		-- domain
		if authority ~= '' and not self.host then
			local host = authority:lower()
			if  string.match(host, '^[%d%a%-%.]+$') ~= nil and
				string.sub(host, 0, 1) ~= '.' and
				string.sub(host, -1) ~= '.' and
				string.find(host, '%.%.') == nil then
				self.host = host
			end
		end
	end

	if self.userinfo then
		local userinfo = self.userinfo
		userinfo = userinfo:gsub(':([^:]*)$', function(v)
				self.password = v
				return ''
		end)
		if string.find(userinfo, "^[%w%+%.]+$") then
			self.user = userinfo
		else
			-- incorrect userinfo
			self.userinfo = nil
			self.user = nil
			self.password = nil
		end
	end

	return authority
end

--- Parse the url into the designated parts.
-- Depending on the url, the following parts can be available:
-- scheme, userinfo, user, password, authority, host, port, path,
-- query, fragment
-- @param url Url string
-- @return a table with the different parts and a few other functions
function M.parse(url)
	local comp = {}
	M.setAuthority(comp, "")
	M.setQuery(comp, "")

	local url = tostring(url or '')
	url = url:gsub('#(.*)$', function(v)
		comp.fragment = v
		return ''
	end)
	url =url:gsub('^([%w][%w%+%-%.]*)%:', function(v)
		comp.scheme = v:lower()
		return ''
	end)
	url = url:gsub('%?(.*)', function(v)
		M.setQuery(comp, v)
		return ''
	end)
	url = url:gsub('^//([^/]*)', function(v)
		M.setAuthority(comp, v)
		return ''
	end)

	comp.path = url:gsub("([^/]+)", function (s) return encode(decode(s), M.options.legal_in_path) end)

	setmetatable(comp, {
		__index = M,
		__tostring = M.build,
		__concat = concat,
		__div = M.addSegment
	})
	return comp
end

--- removes dots and slashes in urls when possible
-- This function will also remove multiple slashes
-- @param path The string representing the path to clean
-- @return a string of the path without unnecessary dots and segments
function M.removeDotSegments(path)
	local fields = {}
	if string.len(path) == 0 then
		return ""
	end
	local startslash = false
	local endslash = false
	if string.sub(path, 1, 1) == "/" then
		startslash = true
	end
	if (string.len(path) > 1 or startslash == false) and string.sub(path, -1) == "/" then
		endslash = true
	end

	path:gsub('[^/]+', function(c) table.insert(fields, c) end)

	local new = {}
	local j = 0

	for i,c in ipairs(fields) do
		if c == '..' then
			if j > 0 then
				j = j - 1
			end
		elseif c ~= "." then
			j = j + 1
			new[j] = c
		end
	end
	local ret = ""
	if #new > 0 and j > 0 then
		ret = table.concat(new, '/', 1, j)
	else
		ret = ""
	end
	if startslash then
		ret = '/'..ret
	end
	if endslash then
		ret = ret..'/'
	end
	return ret
end

local function reducePath(base_path, relative_path)
	if string.sub(relative_path, 1, 1) == "/" then
		return '/' .. string.gsub(relative_path, '^[%./]+', '')
	end
	local path = base_path
	local startslash = string.sub(path, 1, 1) ~= "/";
	if relative_path ~= "" then
		path = (startslash and '' or '/') .. path:gsub("[^/]*$", "")
	end
	path = path .. relative_path
	path = path:gsub("([^/]*%./)", function (s)
		if s ~= "./" then return s else return "" end
	end)
	path = string.gsub(path, "/%.$", "/")
	local reduced
	while reduced ~= path do
		reduced = path
		path = string.gsub(reduced, "([^/]*/%.%./)", function (s)
			if s ~= "../../" then return "" else return s end
		end)
	end
	path = string.gsub(path, "([^/]*/%.%.?)$", function (s)
		if s ~= "../.." then return "" else return s end
	end)
	local reduced
	while reduced ~= path do
		reduced = path
		path = string.gsub(reduced, '^/?%.%./', '')
	end
	return (startslash and '' or '/') .. path
end

--- builds a new url by using the one given as parameter and resolving paths
-- @param other A string or a table representing a url
-- @return a new url table
function M:resolve(other)
	if type(self) == "string" then
		self = M.parse(self)
	end
	if type(other) == "string" then
		other = M.parse(other)
	end
	if other.scheme then
		return other
	else
		other.scheme = self.scheme
		if not other.authority or other.authority == "" then
			other:setAuthority(self.authority)
			if not other.path or other.path == "" then
				other.path = self.path
				local query = other.query
				if not query or not next(query) then
					other.query = self.query
				end
			else
				other.path = reducePath(self.path, other.path)
			end
		end
		return other
	end
end

--- normalize a url path following some common normalization rules
-- described on <a href="http://en.wikipedia.org/wiki/URL_normalization">The URL normalization page of Wikipedia</a>
-- @return the normalized path
function M:normalize()
	if type(self) == 'string' then
		self = M.parse(self)
	end
	if self.path then
		local path = self.path
		path = reducePath(path, "")
		-- normalize multiple slashes
		path = string.gsub(path, "//+", "/")
		self.path = path
	end
	return self
end

return M
