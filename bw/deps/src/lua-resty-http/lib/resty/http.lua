local http_headers = require "resty.http_headers"

local ngx = ngx
local ngx_socket_tcp = ngx.socket.tcp
local ngx_req = ngx.req
local ngx_req_socket = ngx_req.socket
local ngx_req_get_headers = ngx_req.get_headers
local ngx_req_get_method = ngx_req.get_method
local str_lower = string.lower
local str_upper = string.upper
local str_find = string.find
local str_sub = string.sub
local tbl_concat = table.concat
local tbl_insert = table.insert
local ngx_encode_args = ngx.encode_args
local ngx_re_match = ngx.re.match
local ngx_re_gmatch = ngx.re.gmatch
local ngx_re_sub = ngx.re.sub
local ngx_re_gsub = ngx.re.gsub
local ngx_re_find = ngx.re.find
local ngx_log = ngx.log
local ngx_DEBUG = ngx.DEBUG
local ngx_ERR = ngx.ERR
local ngx_var = ngx.var
local ngx_print = ngx.print
local ngx_header = ngx.header
local co_yield = coroutine.yield
local co_create = coroutine.create
local co_status = coroutine.status
local co_resume = coroutine.resume
local setmetatable = setmetatable
local tonumber = tonumber
local tostring = tostring
local unpack = unpack
local rawget = rawget
local select = select
local ipairs = ipairs
local pairs = pairs
local pcall = pcall
local type = type


-- http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.5.1
local HOP_BY_HOP_HEADERS = {
    ["connection"]          = true,
    ["keep-alive"]          = true,
    ["proxy-authenticate"]  = true,
    ["proxy-authorization"] = true,
    ["te"]                  = true,
    ["trailers"]            = true,
    ["transfer-encoding"]   = true,
    ["upgrade"]             = true,
    ["content-length"]      = true, -- Not strictly hop-by-hop, but Nginx will deal
                                    -- with this (may send chunked for example).
}


local EXPECTING_BODY = {
    POST  = true,
    PUT   = true,
    PATCH = true,
}


-- Reimplemented coroutine.wrap, returning "nil, err" if the coroutine cannot
-- be resumed. This protects user code from infinite loops when doing things like
-- repeat
--   local chunk, err = res.body_reader()
--   if chunk then -- <-- This could be a string msg in the core wrap function.
--     ...
--   end
-- until not chunk
local co_wrap = function(func)
    local co = co_create(func)
    if not co then
        return nil, "could not create coroutine"
    else
        return function(...)
            if co_status(co) == "suspended" then
                return select(2, co_resume(co, ...))
            else
                return nil, "can't resume a " .. co_status(co) .. " coroutine"
            end
        end
    end
end


-- Returns a new table, recursively copied from the one given.
--
-- @param   table   table to be copied
-- @return  table
local function tbl_copy(orig)
    local orig_type = type(orig)
    local copy
    if orig_type == "table" then
        copy = {}
        for orig_key, orig_value in next, orig, nil do
            copy[tbl_copy(orig_key)] = tbl_copy(orig_value)
        end
    else -- number, string, boolean, etc
        copy = orig
    end
    return copy
end


local _M = {
    _VERSION = '0.16.1',
}
_M._USER_AGENT = "lua-resty-http/" .. _M._VERSION .. " (Lua) ngx_lua/" .. ngx.config.ngx_lua_version

local mt = { __index = _M }


local HTTP = {
    [1.0] = " HTTP/1.0\r\n",
    [1.1] = " HTTP/1.1\r\n",
}


local DEFAULT_PARAMS = {
    method = "GET",
    path = "/",
    version = 1.1,
}


local DEBUG = false


function _M.new(_)
    local sock, err = ngx_socket_tcp()
    if not sock then
        return nil, err
    end
    return setmetatable({ sock = sock, keepalive = true }, mt)
end


function _M.debug(d)
    DEBUG = (d == true)
end


function _M.set_timeout(self, timeout)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    return sock:settimeout(timeout)
end


function _M.set_timeouts(self, connect_timeout, send_timeout, read_timeout)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    return sock:settimeouts(connect_timeout, send_timeout, read_timeout)
end

do
    local aio_connect = require "resty.http_connect"
    -- Function signatures to support:
    -- ok, err = httpc:connect(options_table)
    -- ok, err = httpc:connect(host, port, options_table?)
    -- ok, err = httpc:connect("unix:/path/to/unix.sock", options_table?)
    function _M.connect(self, options, ...)
        if type(options) == "table" then
            -- all-in-one interface
            return aio_connect(self, options)
        else
            -- backward compatible
            return self:tcp_only_connect(options, ...)
        end
    end
end

function _M.tcp_only_connect(self, ...)
    ngx_log(ngx_DEBUG, "Use of deprecated `connect` method signature")

    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    self.host = select(1, ...)
    self.port = select(2, ...)

    -- If port is not a number, this is likely a unix domain socket connection.
    if type(self.port) ~= "number" then
        self.port = nil
    end

    self.keepalive = true
    self.ssl = false

    return sock:connect(...)
end


function _M.set_keepalive(self, ...)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    if self.keepalive == true then
        return sock:setkeepalive(...)
    else
        -- The server said we must close the connection, so we cannot setkeepalive.
        -- If close() succeeds we return 2 instead of 1, to differentiate between
        -- a normal setkeepalive() failure and an intentional close().
        local res, err = sock:close()
        if res then
            return 2, "connection must be closed"
        else
            return res, err
        end
    end
end


function _M.get_reused_times(self)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    return sock:getreusedtimes()
end


function _M.close(self)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    return sock:close()
end


local function _should_receive_body(method, code)
    if method == "HEAD" then return nil end
    if code == 204 or code == 304 then return nil end
    if code >= 100 and code < 200 then return nil end
    return true
end


function _M.parse_uri(_, uri, query_in_path)
    if query_in_path == nil then query_in_path = true end

    local m, err = ngx_re_match(
        uri,
        [[^(?:(http[s]?):)?//((?:[^\[\]:/\?]+)|(?:\[.+\]))(?::(\d+))?([^\?]*)\??(.*)]],
        "jo"
    )

    if not m then
        if err then
            return nil, "failed to match the uri: " .. uri .. ", " .. err
        end

        return nil, "bad uri: " .. uri
    else
        -- If the URI is schemaless (i.e. //example.com) try to use our current
        -- request scheme.
        if not m[1] then
            -- Schema-less URIs can occur in client side code, implying "inherit
            -- the schema from the current request". We support it for a fairly
            -- specific case; if for example you are using the ESI parser in
            -- ledge (https://github.com/ledgetech/ledge) to perform in-flight
            -- sub requests on the edge based on instructions found in markup,
            -- those URIs may also be schemaless with the intention that the
            -- subrequest would inherit the schema just like JavaScript would.
            local scheme = ngx_var.scheme
            if scheme == "http" or scheme == "https" then
                m[1] = scheme
            else
                return nil, "schemaless URIs require a request context: " .. uri
            end
        end

        if m[3] then
            m[3] = tonumber(m[3])
        else
            if m[1] == "https" then
                m[3] = 443
            else
                m[3] = 80
            end
        end
        if not m[4] or "" == m[4] then m[4] = "/" end

        if query_in_path and m[5] and m[5] ~= "" then
            m[4] = m[4] .. "?" .. m[5]
            m[5] = nil
        end

        return m, nil
    end
end


local function _format_request(self, params)
    local version = params.version
    local headers = params.headers or {}

    local query = params.query or ""
    if type(query) == "table" then
        query = "?" .. ngx_encode_args(query)
    elseif query ~= "" and str_sub(query, 1, 1) ~= "?" then
        query = "?" .. query
    end

    -- Initialize request
    local req = {
        str_upper(params.method),
        " ",
        self.path_prefix or "",
        params.path,
        query,
        HTTP[version],
        -- Pre-allocate slots for minimum headers and carriage return.
        true,
        true,
        true,
    }
    local c = 7 -- req table index it's faster to do this inline vs table.insert

    -- Append headers
    for key, values in pairs(headers) do
        key = tostring(key)

        if type(values) == "table" then
            for _, value in pairs(values) do
                req[c] = key .. ": " .. tostring(value) .. "\r\n"
                c = c + 1
            end

        else
            req[c] = key .. ": " .. tostring(values) .. "\r\n"
            c = c + 1
        end
    end

    -- Close headers
    req[c] = "\r\n"

    return tbl_concat(req)
end


local function _receive_status(sock)
    local line, err = sock:receive("*l")
    if not line then
        return nil, nil, nil, err
    end

    return tonumber(str_sub(line, 10, 12)), tonumber(str_sub(line, 6, 8)), str_sub(line, 14)
end


local function _receive_headers(sock)
    local headers = http_headers.new()

    repeat
        local line, err = sock:receive("*l")
        if not line then
            return nil, err
        end

        local m, err = ngx_re_match(line, "([^:\\s]+):\\s*(.*)", "jo")
        if err then ngx_log(ngx_ERR, err) end

        if not m then
            break
        end

        local key = m[1]
        local val = m[2]
        if headers[key] then
            if type(headers[key]) ~= "table" then
                headers[key] = { headers[key] }
            end
            tbl_insert(headers[key], tostring(val))
        else
            headers[key] = tostring(val)
        end
    until ngx_re_find(line, "^\\s*$", "jo")

    return headers, nil
end


local function transfer_encoding_is_chunked(headers)
    local te = headers["Transfer-Encoding"]
    if not te then
        return false
    end

    -- Handle duplicate headers
    -- This shouldn't happen but can in the real world
    if type(te) ~= "string" then
        te = tbl_concat(te, ",")
    end

    return str_find(str_lower(te), "chunked", 1, true) ~= nil
end
_M.transfer_encoding_is_chunked = transfer_encoding_is_chunked


local function _chunked_body_reader(sock, default_chunk_size)
    return co_wrap(function(max_chunk_size)
        local remaining = 0
        local length
        max_chunk_size = max_chunk_size or default_chunk_size

        repeat
            -- If we still have data on this chunk
            if max_chunk_size and remaining > 0 then

                if remaining > max_chunk_size then
                    -- Consume up to max_chunk_size
                    length = max_chunk_size
                    remaining = remaining - max_chunk_size
                else
                    -- Consume all remaining
                    length = remaining
                    remaining = 0
                end
            else -- This is a fresh chunk

                -- Receive the chunk size
                local str, err = sock:receive("*l")
                if not str then
                    co_yield(nil, err)
                end

                length = tonumber(str, 16)

                if not length then
                    co_yield(nil, "unable to read chunksize")
                end

                if max_chunk_size and length > max_chunk_size then
                    -- Consume up to max_chunk_size
                    remaining = length - max_chunk_size
                    length = max_chunk_size
                end
            end

            if length > 0 then
                local str, err = sock:receive(length)
                if not str then
                    co_yield(nil, err)
                end

                max_chunk_size = co_yield(str) or default_chunk_size

                -- If we're finished with this chunk, read the carriage return.
                if remaining == 0 then
                    sock:receive(2) -- read \r\n
                end
            else
                -- Read the last (zero length) chunk's carriage return
                sock:receive(2) -- read \r\n
            end

        until length == 0
    end)
end


local function _body_reader(sock, content_length, default_chunk_size)
    return co_wrap(function(max_chunk_size)
        max_chunk_size = max_chunk_size or default_chunk_size

        if not content_length and max_chunk_size then
            -- We have no length, but wish to stream.
            -- HTTP 1.0 with no length will close connection, so read chunks to the end.
            repeat
                local str, err, partial = sock:receive(max_chunk_size)
                if not str and err == "closed" then
                    co_yield(partial, err)
                end

                max_chunk_size = tonumber(co_yield(str) or default_chunk_size)
                if max_chunk_size and max_chunk_size < 0 then max_chunk_size = nil end

                if not max_chunk_size then
                    ngx_log(ngx_ERR, "Buffer size not specified, bailing")
                    break
                end
            until not str

        elseif not content_length then
            -- We have no length but don't wish to stream.
            -- HTTP 1.0 with no length will close connection, so read to the end.
            co_yield(sock:receive("*a"))

        elseif not max_chunk_size then
            -- We have a length and potentially keep-alive, but want everything.
            co_yield(sock:receive(content_length))

        else
            -- We have a length and potentially a keep-alive, and wish to stream
            -- the response.
            local received = 0
            repeat
                local length = max_chunk_size
                if received + length > content_length then
                    length = content_length - received
                end

                if length > 0 then
                    local str, err = sock:receive(length)
                    if not str then
                        co_yield(nil, err)
                    end
                    received = received + length

                    max_chunk_size = tonumber(co_yield(str) or default_chunk_size)
                    if max_chunk_size and max_chunk_size < 0 then max_chunk_size = nil end

                    if not max_chunk_size then
                        ngx_log(ngx_ERR, "Buffer size not specified, bailing")
                        break
                    end
                end

            until length == 0
        end
    end)
end


local function _no_body_reader()
    return nil
end


local function _read_body(res)
    local reader = res.body_reader

    if not reader then
        -- Most likely HEAD or 304 etc.
        return nil, "no body to be read"
    end

    local chunks = {}
    local c = 1

    local chunk, err
    repeat
        chunk, err = reader()

        if err then
            return nil, err, tbl_concat(chunks) -- Return any data so far.
        end
        if chunk then
            chunks[c] = chunk
            c = c + 1
        end
    until not chunk

    return tbl_concat(chunks)
end


local function _trailer_reader(sock)
    return co_wrap(function()
        co_yield(_receive_headers(sock))
    end)
end


local function _read_trailers(res)
    local reader = res.trailer_reader
    if not reader then
        return nil, "no trailers"
    end

    local trailers = reader()
    setmetatable(res.headers, { __index = trailers })
end


local function _send_body(sock, body)
    if type(body) == "function" then
        repeat
            local chunk, err, partial = body()

            if chunk then
                local ok, err = sock:send(chunk)

                if not ok then
                    return nil, err
                end
            elseif err ~= nil then
                return nil, err, partial
            end

        until chunk == nil
    elseif body ~= nil then
        local bytes, err = sock:send(body)

        if not bytes then
            return nil, err
        end
    end
    return true, nil
end


local function _handle_continue(sock, body)
    local status, version, reason, err = _receive_status(sock) --luacheck: no unused
    if not status then
        return nil, nil, err
    end

    -- Only send body if we receive a 100 Continue
    if status == 100 then
        local ok, err = sock:receive("*l") -- Read carriage return
        if not ok then
            return nil, nil, err
        end
        _send_body(sock, body)
    end
    return status, version, err
end


function _M.send_request(self, params)
    -- Apply defaults
    setmetatable(params, { __index = DEFAULT_PARAMS })

    local sock = self.sock
    local body = params.body
    local headers = http_headers.new()

    -- We assign one-by-one so that the metatable can handle case insensitivity
    -- for us. You can blame the spec for this inefficiency.
    local params_headers = params.headers or {}
    for k, v in pairs(params_headers) do
        headers[k] = v
    end

    if not headers["Proxy-Authorization"] then
        -- TODO: next major, change this to always override the provided
        -- header. Can't do that yet because it would be breaking.
        -- The connect method uses self.http_proxy_auth in the poolname so
        -- that should be leading.
        headers["Proxy-Authorization"] = self.http_proxy_auth
    end

    -- Ensure we have appropriate message length or encoding.
    do
        local is_chunked = transfer_encoding_is_chunked(headers)

        if is_chunked then
            -- If we have both Transfer-Encoding and Content-Length we MUST
            -- drop the Content-Length, to help prevent request smuggling.
            -- https://tools.ietf.org/html/rfc7230#section-3.3.3
            headers["Content-Length"] = nil

        elseif not headers["Content-Length"] then
            -- A length was not given, try to calculate one.

            local body_type = type(body)

            if body_type == "function" then
                return nil, "Request body is a function but a length or chunked encoding is not specified"

            elseif body_type == "table" then
                local length = 0
                for _, v in ipairs(body) do
                    length = length + #tostring(v)
                end
                headers["Content-Length"] = length

            elseif body == nil and EXPECTING_BODY[str_upper(params.method)] then
                headers["Content-Length"] = 0

            elseif body ~= nil then
                headers["Content-Length"] = #tostring(body)
            end
        end
    end

    if not headers["Host"] then
        if (str_sub(self.host, 1, 5) == "unix:") then
            return nil, "Unable to generate a useful Host header for a unix domain socket. Please provide one."
        end
        -- If we have a port (i.e. not connected to a unix domain socket), and this
        -- port is non-standard, append it to the Host header.
        if self.port then
            if self.ssl and self.port ~= 443 then
                headers["Host"] = self.host .. ":" .. self.port
            elseif not self.ssl and self.port ~= 80 then
                headers["Host"] = self.host .. ":" .. self.port
            else
                headers["Host"] = self.host
            end
        else
            headers["Host"] = self.host
        end
    end
    if not headers["User-Agent"] then
        headers["User-Agent"] = _M._USER_AGENT
    end
    if params.version == 1.0 and not headers["Connection"] then
        headers["Connection"] = "Keep-Alive"
    end

    params.headers = headers

    -- Format and send request
    local req = _format_request(self, params)
    if DEBUG then ngx_log(ngx_DEBUG, "\n", req) end
    local bytes, err = sock:send(req)

    if not bytes then
        return nil, err
    end

    -- Send the request body, unless we expect: continue, in which case
    -- we handle this as part of reading the response.
    if headers["Expect"] ~= "100-continue" then
        local ok, err, partial = _send_body(sock, body)
        if not ok then
            return nil, err, partial
        end
    end

    return true
end


function _M.read_response(self, params)
    local sock = self.sock

    local status, version, reason, err

    -- If we expect: continue, we need to handle this, sending the body if allowed.
    -- If we don't get 100 back, then status is the actual status.
    if params.headers["Expect"] == "100-continue" then
        local _status, _version, _err = _handle_continue(sock, params.body)
        if not _status then
            return nil, _err
        elseif _status ~= 100 then
            status, version, err = _status, _version, _err -- luacheck: no unused
        end
    end

    -- Just read the status as normal.
    if not status then
        status, version, reason, err = _receive_status(sock)
        if not status then
            return nil, err
        end
    end


    local res_headers, err = _receive_headers(sock)
    if not res_headers then
        return nil, err
    end

    -- keepalive is true by default. Determine if this is correct or not.
    local ok, connection = pcall(str_lower, res_headers["Connection"])
    if ok then
        if (version == 1.1 and str_find(connection, "close", 1, true)) or
           (version == 1.0 and not str_find(connection, "keep-alive", 1, true)) then
            self.keepalive = false
        end
    else
        -- no connection header
        if version == 1.0 then
            self.keepalive = false
        end
    end

    local body_reader = _no_body_reader
    local trailer_reader, err
    local has_body = false

    -- Receive the body_reader
    if _should_receive_body(params.method, status) then
        has_body = true

        if version == 1.1 and transfer_encoding_is_chunked(res_headers) then
            body_reader, err = _chunked_body_reader(sock)
        else
            local ok, length = pcall(tonumber, res_headers["Content-Length"])
            if not ok then
                -- No content-length header, read until connection is closed by server
                length = nil
            end

            body_reader, err = _body_reader(sock, length)
        end
    end

    if res_headers["Trailer"] then
        trailer_reader, err = _trailer_reader(sock)
    end

    if err then
        return nil, err
    else
        return {
            status = status,
            reason = reason,
            headers = res_headers,
            has_body = has_body,
            body_reader = body_reader,
            read_body = _read_body,
            trailer_reader = trailer_reader,
            read_trailers = _read_trailers,
        }
    end
end


function _M.request(self, params)
    params = tbl_copy(params) -- Take by value
    local res, err = self:send_request(params)
    if not res then
        return res, err
    else
        return self:read_response(params)
    end
end


function _M.request_pipeline(self, requests)
    requests = tbl_copy(requests) -- Take by value

    for _, params in ipairs(requests) do
        if params.headers and params.headers["Expect"] == "100-continue" then
            return nil, "Cannot pipeline request specifying Expect: 100-continue"
        end

        local res, err = self:send_request(params)
        if not res then
            return res, err
        end
    end

    local responses = {}
    for i, params in ipairs(requests) do
        responses[i] = setmetatable({
            params = params,
            response_read = false,
        }, {
            -- Read each actual response lazily, at the point the user tries
            -- to access any of the fields.
            __index = function(t, k)
                local res, err
                if t.response_read == false then
                    res, err = _M.read_response(self, t.params)
                    t.response_read = true

                    if not res then
                        ngx_log(ngx_ERR, err)
                    else
                        for rk, rv in pairs(res) do
                            t[rk] = rv
                        end
                    end
                end
                return rawget(t, k)
            end,
        })
    end
    return responses
end


function _M.request_uri(self, uri, params)
    params = tbl_copy(params or {}) -- Take by value
    if self.proxy_opts then
        params.proxy_opts = tbl_copy(self.proxy_opts or {})
    end

    do
        local parsed_uri, err = self:parse_uri(uri, false)
        if not parsed_uri then
            return nil, err
        end

        local path, query
        params.scheme, params.host, params.port, path, query = unpack(parsed_uri)
        params.path = params.path or path
        params.query = params.query or query
        params.ssl_server_name = params.ssl_server_name or params.host
    end

    do
        local proxy_auth = (params.headers or {})["Proxy-Authorization"]
        if proxy_auth and params.proxy_opts then
            params.proxy_opts.https_proxy_authorization = proxy_auth
            params.proxy_opts.http_proxy_authorization = proxy_auth
        end
    end

    local ok, err = self:connect(params)
    if not ok then
        return nil, err
    end

    local res, err = self:request(params)
    if not res then
        self:close()
        return nil, err
    end

    local body, err = res:read_body()
    if not body then
        self:close()
        return nil, err
    end

    res.body = body

    if params.keepalive == false then
        local ok, err = self:close()
        if not ok then
            ngx_log(ngx_ERR, err)
        end

    else
        local ok, err = self:set_keepalive(params.keepalive_timeout, params.keepalive_pool)
        if not ok then
            ngx_log(ngx_ERR, err)
        end

    end

    return res, nil
end


function _M.get_client_body_reader(_, chunksize, sock)
    chunksize = chunksize or 65536

    if not sock then
        local ok, err
        ok, sock, err = pcall(ngx_req_socket)

        if not ok then
            return nil, sock -- pcall err
        end

        if not sock then
            if err == "no body" then
                return nil
            else
                return nil, err
            end
        end
    end

    local headers = ngx_req_get_headers()
    local length = headers.content_length
    if length then
        return _body_reader(sock, tonumber(length), chunksize)
    elseif transfer_encoding_is_chunked(headers) then
        -- Not yet supported by ngx_lua but should just work...
        return _chunked_body_reader(sock, chunksize)
    else
        return nil
    end
end


function _M.set_proxy_options(self, opts)
    -- TODO: parse and cache these options, instead of parsing them
    -- on each request over and over again (lru-cache on module level)
    self.proxy_opts = tbl_copy(opts) -- Take by value
end


function _M.get_proxy_uri(self, scheme, host)
    if not self.proxy_opts then
        return nil
    end

    -- Check if the no_proxy option matches this host. Implementation adapted
    -- from lua-http library (https://github.com/daurnimator/lua-http)
    if self.proxy_opts.no_proxy then
        if self.proxy_opts.no_proxy == "*" then
            -- all hosts are excluded
            return nil
        end

        local no_proxy_set = {}
        -- wget allows domains in no_proxy list to be prefixed by "."
        -- e.g. no_proxy=.mit.edu
        for host_suffix in ngx_re_gmatch(self.proxy_opts.no_proxy, "\\.?([^,]+)", "jo") do
            no_proxy_set[host_suffix[1]] = true
        end

        -- From curl docs:
        -- matched as either a domain which contains the hostname, or the
        -- hostname itself. For example local.com would match local.com,
        -- local.com:80, and www.local.com, but not www.notlocal.com.
        --
        -- Therefore, we keep stripping subdomains from the host, compare
        -- them to the ones in the no_proxy list and continue until we find
        -- a match or until there's only the TLD left
        repeat
            if no_proxy_set[host] then
                return nil
            end

            -- Strip the next level from the domain and check if that one
            -- is on the list
            host = ngx_re_sub(host, "^[^.]+\\.", "", "jo")
        until not ngx_re_find(host, "\\.", "jo")
    end

    if scheme == "http" and self.proxy_opts.http_proxy then
        return self.proxy_opts.http_proxy
    end

    if scheme == "https" and self.proxy_opts.https_proxy then
        return self.proxy_opts.https_proxy
    end

    return nil
end


-- ----------------------------------------------------------------------------
-- The following functions are considered DEPRECATED and may be REMOVED in
-- future releases. Please see the notes in `README.md`.
-- ----------------------------------------------------------------------------

function _M.ssl_handshake(self, ...)
    ngx_log(ngx_DEBUG, "Use of deprecated function `ssl_handshake`")

    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    self.ssl = true

    return sock:sslhandshake(...)
end


function _M.connect_proxy(self, proxy_uri, scheme, host, port, proxy_authorization)
    ngx_log(ngx_DEBUG, "Use of deprecated function `connect_proxy`")

    -- Parse the provided proxy URI
    local parsed_proxy_uri, err = self:parse_uri(proxy_uri, false)
    if not parsed_proxy_uri then
        return nil, err
    end

    -- Check that the scheme is http (https is not supported for
    -- connections between the client and the proxy)
    local proxy_scheme = parsed_proxy_uri[1]
    if proxy_scheme ~= "http" then
        return nil, "protocol " .. proxy_scheme .. " not supported for proxy connections"
    end

    -- Make the connection to the given proxy
    local proxy_host, proxy_port = parsed_proxy_uri[2], parsed_proxy_uri[3]
    local c, err = self:tcp_only_connect(proxy_host, proxy_port)
    if not c then
        return nil, err
    end

    if scheme == "https" then
        -- Make a CONNECT request to create a tunnel to the destination through
        -- the proxy. The request-target and the Host header must be in the
        -- authority-form of RFC 7230 Section 5.3.3. See also RFC 7231 Section
        -- 4.3.6 for more details about the CONNECT request
        local destination = host .. ":" .. port
        local res, err = self:request({
            method = "CONNECT",
            path = destination,
            headers = {
                ["Host"] = destination,
                ["Proxy-Authorization"] = proxy_authorization,
            }
        })

        if not res then
            return nil, err
        end

        if res.status < 200 or res.status > 299 then
            return nil, "failed to establish a tunnel through a proxy: " .. res.status
        end
    end

    return c, nil
end


function _M.proxy_request(self, chunksize)
    ngx_log(ngx_DEBUG, "Use of deprecated function `proxy_request`")

    return self:request({
        method = ngx_req_get_method(),
        path = ngx_re_gsub(ngx_var.uri, "\\s", "%20", "jo") .. ngx_var.is_args .. (ngx_var.query_string or ""),
        body = self:get_client_body_reader(chunksize),
        headers = ngx_req_get_headers(),
    })
end


function _M.proxy_response(_, response, chunksize)
    ngx_log(ngx_DEBUG, "Use of deprecated function `proxy_response`")

    if not response then
        ngx_log(ngx_ERR, "no response provided")
        return
    end

    ngx.status = response.status

    -- Filter out hop-by-hop headeres
    for k, v in pairs(response.headers) do
        if not HOP_BY_HOP_HEADERS[str_lower(k)] then
            ngx_header[k] = v
        end
    end

    local reader = response.body_reader

    repeat
        local chunk, ok, read_err, print_err

        chunk, read_err = reader(chunksize)
        if read_err then
            ngx_log(ngx_ERR, read_err)
        end

        if chunk then
            ok, print_err = ngx_print(chunk)
            if not ok then
                ngx_log(ngx_ERR, print_err)
            end
        end

        if read_err or print_err then
            break
        end
    until not chunk
end


return _M
