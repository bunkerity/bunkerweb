-------------------------------------------------------------------------------
-- Syslog for LuaLogging to a remote server using UDP/TCP
--
-- @author Thijs Schreijer
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

-- This module differs from [`LuaSyslog`](https://github.com/lunarmodules/luasyslog)
-- in that it will log to a remote server, where `LuaSyslog` will log to the local
-- syslog daemon.


local socket = require "socket"
local logging = require "logging"
local prepareLogMsg = logging.prepareLogMsg
local pcall = pcall


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


-- set on module table to be able to override it. For example with a Copas
-- socket. No need for UDP, since UDP sending is non-blocking.
M.tcp = socket.tcp


local NILVALUE = "-"
local MONTHS = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" }


-- determine the local machine hostname, once at startup
local HOSTNAME do
  if _G.package.config:sub(1,1) == "\\" then
    -- Windows
    HOSTNAME = os.getenv("COMPUTERNAME")
  else
    -- Unix like
    local f = io.popen ("/bin/hostname")
    HOSTNAME = f:read("*a")
    f:close()
  end

  HOSTNAME = (HOSTNAME or ""):gsub("[^\33-\126]", "")

  if HOSTNAME == "" then
    local s = socket.udp()
    s:setpeername("1.1.1.1",80) -- ip for cloudflare dns
    HOSTNAME = s:getsockname()
  end

  HOSTNAME = (HOSTNAME or ""):gsub("[^\33-\126]", "")

  if HOSTNAME == "" then
    HOSTNAME = NILVALUE
  end
end



-- the syslog constants
local syslog_facilities = {
  FACILITY_KERN = 0 * 8,
  FACILITY_USER = 1 * 8,
  FACILITY_MAIL = 2 * 8,
  FACILITY_DAEMON = 3 * 8,
  FACILITY_AUTH = 4 * 8,
  FACILITY_SYSLOG = 5 * 8,
  FACILITY_LPR = 6 * 8,
  FACILITY_NEWS = 7 * 8,
  FACILITY_UUCP = 8 * 8,
  FACILITY_CRON = 9 * 8,
  FACILITY_AUTHPRIV = 10 * 8,
  FACILITY_FTP = 11 * 8,
  FACILITY_NTP = 12 * 8,
  FACILITY_SECURITY = 13 * 8,
  FACILITY_CONSOLE = 14 * 8,
  FACILITY_NETINFO = 12 * 8,
  FACILITY_REMOTEAUTH = 13 * 8,
  FACILITY_INSTALL = 14 * 8,
  FACILITY_RAS = 15 * 8,
  FACILITY_LOCAL0 = 16 * 8,
  FACILITY_LOCAL1 = 17 * 8,
  FACILITY_LOCAL2 = 18 * 8,
  FACILITY_LOCAL3 = 19 * 8,
  FACILITY_LOCAL4 = 20 * 8,
  FACILITY_LOCAL5 = 21 * 8,
  FACILITY_LOCAL6 = 22 * 8,
  FACILITY_LOCAL7 = 23 * 8,
}
for k,v in pairs(syslog_facilities) do
  M[k] = v
end



local syslog_levels = {
  LOG_EMERG = 0,
  LOG_ALERT = 1,
  LOG_CRIT = 2,
  LOG_ERR = 3,
  LOG_WARNING = 4,
  LOG_NOTICE = 5,
  LOG_INFO = 6,
  LOG_DEBUG = 7,
}


-- lookup table: convert lualogging level constant to syslog level constant
local convert = {
	[logging.DEBUG] = syslog_levels.LOG_DEBUG,
	[logging.INFO]  = syslog_levels.LOG_INFO,
	[logging.WARN]  = syslog_levels.LOG_WARNING,
	[logging.ERROR] = syslog_levels.LOG_ERR,
	[logging.FATAL] = syslog_levels.LOG_ALERT,
}


-- ---------------------------------------------------------------------------
-- Writer functions for both RFC's
-- ---------------------------------------------------------------------------
M.writers = {}


function M.writers.rfc3164(prio, facility, ident, _, _, msg)
  local d = os.date("!*t")
  msg = msg:gsub("\n", "\\n"):gsub("\t", " "):gsub("\0-\31", "") -- higher bytes allowed, for UTF8... not according to spec
  return ("<%d>%s %2d %02d:%02d:%02d %s %s %s\n"):format(facility + prio, MONTHS[d.month], d.day, d.hour, d.min, d.sec, HOSTNAME, ident, msg)
end


function M.writers.rfc5424(prio, facility, ident, procid, msgid, msg)
  local timestamp = logging.date("!%Y-%m-%dT%H:%M:%S.%qZ")
  return ("<%d>1 %s %s %s %s %s - %s"):format(facility + prio, timestamp, HOSTNAME, ident, procid, msgid, msg)
end


-- ---------------------------------------------------------------------------
-- sender functions for UDP and TCP
-- ---------------------------------------------------------------------------

M.senders = {}

-- sockets indexed by cache-key.
-- NOTE: sockets should be anchored on the logger object to prevent GC
-- of active ones.
local socket_cache = setmetatable({}, { __mode = "v" })



local function socket_error(self, err)
  io.stderr:write(err.."\n")
  return nil, err
end



function M.senders.udp(self, msg, is_retry)
  local sock = self.socket
  if not sock then
    local cache_key = self.socket_cache_key
    sock = socket_cache[cache_key]
    if not sock then
      -- create a new socket
      local host, port = cache_key:match("^udp://(.+):(%d+)$")
      sock = assert(socket.udp())
      assert(sock:settimeout(5))
      local ok, err = sock:setpeername(host, tonumber(port))
      if not ok then
        return socket_error(self, "failed to connect to "..cache_key..": ".. tostring(err).."\n"..tostring(msg))
      end
      -- cache it
      socket_cache[cache_key] = sock
    end
    -- anchor it
    self.socket = sock
  end

  local ok, err = sock:send(msg)
  if not ok then
    sock:close()
    self.socket = nil
    socket_cache[self.socket_cache_key] = nil
    -- recurse once; will recreate the socket and retry
    if not is_retry then
      return M.senders.udp(self, msg, true)
    else
      return socket_error(self, "failed to send msg (after retry) to "..self.socket_cache_key..": ".. tostring(err).."\n"..tostring(msg))
    end
  end
  return true
end



function M.senders.tcp(self, msg, is_retry)
  local sock = self.socket
  if not sock then
    local cache_key = self.socket_cache_key
    sock = socket_cache[cache_key]
    if not sock then
      -- create a new socket
      local host, port = cache_key:match("^tcp://(.+):(%d+)$")
      sock = assert(M.tcp())
      assert(sock:settimeout(5))
      local ok, err = sock:connect(host, tonumber(port))
      if not ok then
        return socket_error(self, "failed to connect to "..cache_key..": ".. tostring(err).."\n"..tostring(msg))
      end
      ok, err = sock:setoption("keepalive", true)
      if not ok then
        return socket_error(self, "failed to set keepalive for "..cache_key..": ".. tostring(err).."\n"..tostring(msg))
      end
      -- cache it
      socket_cache[cache_key] = sock
    end
    -- anchor it
    self.socket = sock
  end

  local payload
  if self.send_msg_size then
    payload = ("%d %s"):format(#msg, msg)
  else
    payload = msg.."\n"  -- old RFC, terminate by LF
  end
  local last_byte_send = 0
  local size = #payload
  local err, last_send_error
  while last_byte_send < size do
    last_byte_send, err, last_send_error = sock:send(payload, last_byte_send + 1, size)
    if not last_byte_send then
      sock:close()
      self.socket = nil
      socket_cache[self.socket_cache_key] = nil
      -- recurse once; will recreate the socket and retry
      if not is_retry then
        return M.senders.tcp(self, msg, true)
      else
        return socket_error(self, "failed to send msg (after retry) to "..self.socket_cache_key.." ("..tostring(last_send_error).." bytes sent): ".. tostring(err).."\n"..tostring(msg))
      end
    end
  end
  return true
end



function M.senders.copas(self, msg)
  local q = self.queue
  q:push(msg)
  if q:get_size() >= 1000 then
    -- queue is running full, drop an old message
    q:pop()
  end
end



-- ---------------------------------------------------------------------------
-- instantiation
-- ---------------------------------------------------------------------------


local function validate_facility(f)
  for k, v in pairs(syslog_facilities) do
    if v == f then
      if tostring(k):find("FACILITY_") then
        return f
      end
    end
  end
  return nil, "bad facility; " .. tostring(f)
end


local function copas_tcp()
  local copas = require("copas")
  return copas.wrap(socket.tcp())
end


function M.new(params, ...)
  params = logging.getDeprecatedParams({ "ident", "facility" }, params, ...)
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern or "%message")
  local startLevel = params.logLevel or logging.defaultLevel()
  local ident = (params.ident or "lua"):gsub("[^\33-\126]", "")
  assert(#ident > 0 and ident == (params.ident or "lua"), "invalid ident; invalid characters or empty")
  local procid = (params.procid or NILVALUE):gsub("[^\33-\126]", "")
  assert(#procid > 0 and procid == (params.procid or NILVALUE), "invalid procid; invalid characters or empty")
  local msgid = (params.msgid or NILVALUE):gsub("[^\33-\126]", "")
  assert(#msgid > 0 and msgid == (params.msgid or NILVALUE), "invalid msgid invalid characters or empty")
  local facility = assert(validate_facility(params.facility or syslog_facilities.FACILITY_USER))
  local maxsize = tonumber(params.maxsize)
  local write = assert(M.writers[params.rfc or "rfc3164"], "unsupported format: "..tostring(params.rfc))

  if not maxsize then
    maxsize = 2048
    if params.rfc == "rfc3164" then
      maxsize = 1024
    end
  end
  assert(maxsize > 480, "expected maxsize to be a number > 480")

  -- if send_msg_size is truthy then the message will be prefixed by the length. Otherwise
  -- an "\n" will be appended as separator. Only applies to TCP.
  local send_msg_size = false
  if params.rfc == "rfc5424" then
    send_msg_size = true
  end

  local port = params.port or 514
  assert(type(port) == "number" and port > 0 and port < 65535, "not a valid port number: " .. tostring(params.port))
  local hostname = params.hostname
  assert(type(hostname) == "string", "expected 'hostname' to be a string")

  local protocol = params.protocol
  local send = assert(M.senders[protocol or "tcp"], "unsupported protocol: "..tostring(protocol))
  if protocol == "tcp" and M.tcp == copas_tcp then
    -- copas was enabled, so use copas instead of tcp
    send = M.senders.copas
  end

  local new_logger = logging.new(function(self, level, message)
    message = prepareLogMsg(logPatterns[level], "", level, message)
    message = write(convert[level], facility, ident, procid, msgid, message)

    send(self, message:sub(1, maxsize))
    return true
  end, startLevel)

  -- set some logger properties
  new_logger.socket_cache_key = ("%s://%s:%d"):format(protocol, hostname, port)
  new_logger.send_msg_size = send_msg_size

  if protocol == "tcp" and M.tcp == copas_tcp then
    -- a copas sender, needs an async queue, and a worker to process the messages
    local queue = require("copas.queue").new {
      name = "lualogging-rsyslog"
    }
    local tcp_sender = M.senders.tcp
    queue:add_worker(function(msg)
      local ok, err = pcall(tcp_sender, new_logger, msg)
      if not ok then
        socket_error(new_logger, "lualogging rsyslog failed logging through Copas socket: "..tostring(err).."\n"..tostring(msg))
      end
    end)
    new_logger.queue = queue
    function new_logger:destroy()
      if self.queue then
        self.queue:stop()
        self.queue = nil
      end
    end
  end

  return new_logger
end

function M.copas()
  if _VERSION=="Lua 5.1" and not jit then  -- prevent yield across c-boundary
    pcall = require("coxpcall").pcall
  end

  M.tcp = copas_tcp
end

logging.rsyslog = M
return M
