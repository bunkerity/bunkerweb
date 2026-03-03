---
-- OCSP stapling for dynamically loaded SSL certificates.
--
-- NGINX's built-in ssl_stapling directive does not work when certificates are
-- set via ssl_certificate_by_lua because the certs are not known at config
-- time.  This module bridges the gap by pre-fetching OCSP responses in a
-- background timer and attaching cached responses during the TLS handshake.
--
-- Architecture (two-phase, non-blocking):
--
--   1. BACKGROUND TIMER (init_worker → ngx.timer.every)
--      Iterates over PEM cert chains stored in the "ocsp_stapling" shared dict
--      (keys prefixed "pem:<sni>"), contacts each certificate's OCSP responder,
--      validates the response, and caches it under "resp:<sni>".
--
--   2. HANDSHAKE (ssl_certificate_by_lua)
--      After setting the cert/key, calls set_from_cache(sni) which reads the
--      pre-cached response from the shared dict and calls
--      ocsp.set_ocsp_status_resp().  Zero network I/O during the handshake.
--
-- Shared dict key layout:
--   "pem:<sni>"          → raw PEM cert chain (written by plugin load_data)
--   "resp:<sni>"         → validated OCSP response binary, or "NONE" on failure
--   "lock:refresh"       → cross-worker mutex so only one worker fetches at a time
--
-- Failure handling:
--   Every failure caches "NONE" for CACHE_NEG_TTL seconds to avoid hammering a
--   broken responder.  All public entry points are designed to be called via
--   pcall so that errors never disrupt the TLS handshake or worker lifecycle.
---

local ssl = require "ngx.ssl"
local ocsp = require "ngx.ocsp"

local _M = {}

local CACHE_TTL = 3600        -- valid OCSP response lifetime in cache (1 hour)
local CACHE_NEG_TTL = 120     -- negative/failed result lifetime (2 minutes)
local HTTP_TIMEOUT = 5000     -- connect + read timeout for OCSP responder (ms)
local MAX_RESP_SIZE = 102400  -- reject OCSP responses larger than 100 KB
local REFRESH_INTERVAL = 3600 -- how often the background timer re-fetches (1 hour)

local ngx = ngx

--- Extract host, numeric port, and path from an HTTP(S) URL.
-- @param  url  string  e.g. "http://ocsp.sectigo.com"
-- @return host, port, path  or  nil, nil, nil, err
local function parse_url(url)
	local host, port, path = url:match("^https?://([^/:]+):?(%d*)(.*)$")
	if not host then
		return nil, nil, nil, "invalid URL"
	end
	port = tonumber(port) or 80
	if not path or path == "" then
		path = "/"
	end
	return host, port, path
end

--- Minimal HTTP/1.0 POST using cosockets (resty.http is not bundled).
-- Used exclusively from background timers, never during the TLS handshake.
-- @param  host  string   target hostname
-- @param  port  number   target port
-- @param  path  string   request path
-- @param  body  string   raw request body (DER-encoded OCSP request)
-- @return body string on success, or nil + error string
local function http_post(host, port, path, body)
	local sock = ngx.socket.tcp()
	sock:settimeout(HTTP_TIMEOUT)

	local ok, err = sock:connect(host, port)
	if not ok then
		return nil, "connect: " .. err
	end

	local req = "POST " .. path .. " HTTP/1.0\r\n"
		.. "Host: " .. host .. "\r\n"
		.. "Content-Type: application/ocsp-request\r\n"
		.. "Content-Length: " .. #body .. "\r\n"
		.. "Connection: close\r\n"
		.. "\r\n"
		.. body

	local bytes, send_err = sock:send(req)
	if not bytes then
		sock:close()
		return nil, "send: " .. send_err
	end

	local status_line, recv_err = sock:receive("*l")
	if not status_line then
		sock:close()
		return nil, "receive status: " .. recv_err
	end

	local status = tonumber(status_line:match("HTTP/%d%.%d (%d+)"))
	if not status then
		sock:close()
		return nil, "invalid status line"
	end

	if status ~= 200 then
		sock:close()
		return nil, "HTTP " .. status
	end

	local content_length
	while true do
		local line, hdr_err = sock:receive("*l")
		if not line then
			sock:close()
			return nil, "receive header: " .. hdr_err
		end
		if line == "" then
			break
		end
		local cl = line:match("^[Cc]ontent%-[Ll]ength:%s*(%d+)")
		if cl then
			content_length = tonumber(cl)
		end
	end

	local resp_body, body_err
	if content_length then
		if content_length > MAX_RESP_SIZE then
			sock:close()
			return nil, "response too large: " .. content_length
		end
		resp_body, body_err = sock:receive(content_length)
	else
		resp_body, body_err = sock:receive("*a")
	end
	sock:close()

	if not resp_body then
		return nil, "receive body: " .. (body_err or "unknown")
	end

	return resp_body
end

--- Fetch and cache the OCSP response for a single certificate.
-- Called from the background timer for each "pem:<sni>" entry.
-- Skips the fetch if a valid (non-"NONE") response is already cached.
local function fetch_one(pem, sni)
	local cache = ngx.shared.ocsp_stapling
	local resp_key = "resp:" .. sni

	local existing = cache:get(resp_key)
	if existing and existing ~= "NONE" then
		return
	end

	local der_cert_chain, err = ssl.cert_pem_to_der(pem)
	if not der_cert_chain then
		ngx.log(ngx.WARN, "OCSP stapling: PEM-to-DER failed for ", sni, ": ", err)
		cache:set(resp_key, "NONE", CACHE_NEG_TTL)
		return
	end

	local ocsp_url
	ocsp_url, err = ocsp.get_ocsp_responder_from_der_chain(der_cert_chain)
	if not ocsp_url then
		cache:set(resp_key, "NONE", CACHE_NEG_TTL)
		return
	end

	local ocsp_req
	ocsp_req, err = ocsp.create_ocsp_request(der_cert_chain)
	if not ocsp_req then
		ngx.log(ngx.WARN, "OCSP stapling: create request failed for ", sni, ": ", err)
		cache:set(resp_key, "NONE", CACHE_NEG_TTL)
		return
	end

	local host, port, path, parse_err = parse_url(ocsp_url)
	if not host then
		ngx.log(ngx.WARN, "OCSP stapling: bad URL ", ocsp_url, ": ", (parse_err or "?"))
		cache:set(resp_key, "NONE", CACHE_NEG_TTL)
		return
	end

	local ocsp_resp
	ocsp_resp, err = http_post(host, port, path, ocsp_req)
	if not ocsp_resp or #ocsp_resp == 0 then
		ngx.log(ngx.WARN, "OCSP stapling: fetch failed for ", sni, " (", ocsp_url, "): ", (err or "empty"))
		cache:set(resp_key, "NONE", CACHE_NEG_TTL)
		return
	end

	local ok
	ok, err = ocsp.validate_ocsp_response(ocsp_resp, der_cert_chain)
	if not ok then
		ngx.log(ngx.WARN, "OCSP stapling: validation failed for ", sni, ": ", err)
		cache:set(resp_key, "NONE", CACHE_NEG_TTL)
		return
	end

	cache:set(resp_key, ocsp_resp, CACHE_TTL)
	ngx.log(ngx.INFO, "OCSP stapling: cached response for ", sni, " via ", ocsp_url)
end

--- Background timer callback: refresh OCSP responses for all registered certs.
-- Acquires a shared-dict lock so only one NGINX worker performs the refresh
-- cycle; other workers simply read the shared cache populated by the winner.
local function refresh_all(premature)
	if premature then
		return
	end

	local cache = ngx.shared.ocsp_stapling
	if not cache then
		return
	end

	local ok, err = cache:add("lock:refresh", true, REFRESH_INTERVAL - 60)
	if not ok then
		return
	end

	local keys = cache:get_keys(1024)
	for _, key in ipairs(keys) do
		local sni = key:match("^pem:(.+)$")
		if sni then
			local pem = cache:get(key)
			if pem then
				local ok_fetch, fetch_err = pcall(fetch_one, pem, sni)
				if not ok_fetch then
					ngx.log(ngx.WARN, "OCSP stapling: error for ", sni, ": ", tostring(fetch_err))
				end
			end
		end
	end
end

--- Attach a pre-cached OCSP response to the current TLS handshake.
-- Called from ssl_certificate_by_lua after the certificate and private key
-- have been set.  Performs no network I/O — only a shared dict read and an
-- FFI call to set_ocsp_status_resp().
-- @param sni  string  the SNI hostname from the ClientHello
function _M.set_from_cache(sni)
	local cache = ngx.shared.ocsp_stapling
	if not cache or not sni then
		return
	end

	local cached_resp = cache:get("resp:" .. sni)
	if not cached_resp or cached_resp == "NONE" then
		return
	end

	local ok, err = ocsp.set_ocsp_status_resp(cached_resp)
	if not ok then
		ngx.log(ngx.WARN, "OCSP stapling: set response failed for ", sni, ": ", err)
	end
end

local timer_started = false

--- Start the recurring background refresh timer.
-- Safe to call multiple times; subsequent calls are no-ops.  Intended to be
-- called from init_worker_by_lua after all plugin init_worker() methods have
-- loaded their certificates (so the "pem:*" keys are populated).
function _M.start_refresh()
	if timer_started then
		return
	end
	timer_started = true

	ngx.timer.at(0, refresh_all)
	local ok, err = ngx.timer.every(REFRESH_INTERVAL, refresh_all)
	if not ok then
		ngx.log(ngx.WARN, "OCSP stapling: failed to create recurring timer: ", err)
		timer_started = false
	end
end

return _M
