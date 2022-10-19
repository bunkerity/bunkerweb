local require      = require

local random       = require "resty.random"

local ngx          = ngx
local var          = ngx.var
local time         = ngx.time
local header       = ngx.header
local http_time    = ngx.http_time
local set_header   = ngx.req.set_header
local clear_header = ngx.req.clear_header
local concat       = table.concat
local ceil         = math.ceil
local max          = math.max
local find         = string.find
local gsub         = string.gsub
local byte         = string.byte
local sub          = string.sub
local type         = type
local pcall        = pcall
local tonumber     = tonumber
local setmetatable = setmetatable
local getmetatable = getmetatable
local bytes        = random.bytes

local UNDERSCORE = byte("_")
local EXPIRE_FLAGS = "; Expires=Thu, 01 Jan 1970 00:00:01 GMT; Max-Age=0"

local COOKIE_PARTS = {
    DEFAULT = {
        n = 3,
        "id",
        "expires", -- may also contain: `expires:usebefore`
        "hash"
    },
    cookie = {
        n = 4,
        "id",
        "expires", -- may also contain: `expires:usebefore`
        "data",
        "hash",
    },
}

local function enabled(value)
    if value == nil then
        return nil
    end

    return value == true
        or value == "1"
        or value == "true"
        or value == "on"
end

local function ifnil(value, default)
    if value == nil then
        return default
    end

    return enabled(value)
end

local function prequire(prefix, package, default)
    if type(package) == "table" then
        return package, package.name
    end

    local ok, module = pcall(require, prefix .. package)
    if not ok then
        return require(prefix .. default), default
    end

    return module, package
end

local function is_session_cookie(cookie, name, name_len)
    if not cookie or cookie == "" then
        return false, nil
    end

    cookie = gsub(cookie, "^%s+", "")
    if cookie == "" then
        return false, nil
    end

    cookie = gsub(cookie, "%s+$", "")
    if cookie == "" then
        return false, nil
    end

    local eq_pos = find(cookie, "=", 1, true)
    if not eq_pos then
        return false, cookie
    end

    local cookie_name = sub(cookie, 1, eq_pos - 1)
    if cookie_name == "" then
        return false, cookie
    end

    cookie_name = gsub(cookie_name, "%s+$", "")
    if cookie_name == "" then
        return false, cookie
    end

    if cookie_name ~= name then
        if find(cookie_name, name, 1, true) ~= 1 then
            return false, cookie
        end

        if byte(cookie_name, name_len + 1) ~= UNDERSCORE then
            return false, cookie
        end

        if not tonumber(sub(cookie_name, name_len + 2), 10) then
            return false, cookie
        end
    end

    return true, cookie
end

local function set_cookie(session, value, expires)
    if ngx.headers_sent then
        return nil, "attempt to set session cookie after sending out response headers"
    end

    value = value or ""

    local cookie = session.cookie
    local output = {}

    local i = 3

     -- build cookie parameters, elements 1+2 will be set later
    if expires then
        -- we're expiring/deleting the data, so set an expiry in the past
        output[i] = EXPIRE_FLAGS
    elseif cookie.persistent then
        -- persistent cookies have an expiry
        output[i]   = "; Expires="  .. http_time(session.expires) .. "; Max-Age=" .. cookie.lifetime
    else
        -- just to reserve index 3 for expiry as cookie might get smaller,
        -- and some cookies need to be expired.
        output[i] = ""
    end

    if cookie.domain and cookie.domain ~= "localhost" and cookie.domain ~= "" then
        i = i + 1
        output[i]   = "; Domain=" .. cookie.domain
    end

    i = i + 1
    output[i] = "; Path=" .. (cookie.path or "/")

    if cookie.samesite == "Lax"
    or cookie.samesite == "Strict"
    or cookie.samesite == "None"
    then
        i = i + 1
        output[i] = "; SameSite=" .. cookie.samesite
    end

    if cookie.secure then
        i = i + 1
        output[i] = "; Secure"
    end

    if cookie.httponly then
        i = i + 1
        output[i] = "; HttpOnly"
    end

    -- How many chunks do we need?
    local cookie_parts
    local cookie_chunks
    if expires then
        -- expiring cookie, so deleting data. Do not measure data, but use
        -- existing chunk count to make sure we clear all of them
        cookie_parts = cookie.chunks or 1
    else
        -- calculate required chunks from data
        cookie_chunks = max(ceil(#value / cookie.maxsize), 1)
        cookie_parts = max(cookie_chunks, cookie.chunks or 1)
    end

    local cookie_header = header["Set-Cookie"]
    for j = 1, cookie_parts do
        -- create numbered chunk names if required
        local chunk_name = { session.name }
        if j > 1 then
            chunk_name[2] = "_"
            chunk_name[3] = j
            chunk_name[4] = "="
        else
            chunk_name[2] = "="
        end
        chunk_name = concat(chunk_name)
        output[1] = chunk_name

        if expires then
            -- expiring cookie, so deleting data; clear it
            output[2] = ""
        elseif j > cookie_chunks then
            -- less chunks than before, clearing excess cookies
            output[2] = ""
            output[3] = EXPIRE_FLAGS

        else
            -- grab the piece for the current chunk
            local sp = j * cookie.maxsize - (cookie.maxsize - 1)
            if j < cookie_chunks then
                output[2] = sub(value, sp, sp + (cookie.maxsize - 1)) .. "0"
            else
                output[2] = sub(value, sp)
            end
        end

        -- build header value and add it to the header table/string
        -- replace existing chunk-name, or append
        local cookie_content = concat(output)
        local header_type    = type(cookie_header)
        if header_type == "table" then
            local found = false
            local cookie_count = #cookie_header
            for cookie_index = 1, cookie_count do
                if find(cookie_header[cookie_index], chunk_name, 1, true) == 1 then
                    cookie_header[cookie_index] = cookie_content
                    found = true
                    break
                end
            end
            if not found then
                cookie_header[cookie_count + 1] = cookie_content
            end
        elseif header_type == "string" and find(cookie_header, chunk_name, 1, true) ~= 1  then
            cookie_header = { cookie_header, cookie_content }
        else
            cookie_header = cookie_content
        end
    end

    header["Set-Cookie"] = cookie_header

    return true
end

local function get_cookie(session, i)
    local cookie_name = { "cookie_", session.name }
    if i then
        cookie_name[3] = "_"
        cookie_name[4] = i
    else
        i = 1
    end

    local cookie = var[concat(cookie_name)]
    if not cookie then
        return nil
    end

    session.cookie.chunks = i

    local cookie_size = #cookie
    if cookie_size <= session.cookie.maxsize then
        return cookie
    end

    return concat{ sub(cookie, 1, session.cookie.maxsize), get_cookie(session, i + 1) or "" }
end

local function set_usebefore(session)
    local usebefore = session.usebefore
    local idletime  = session.cookie.idletime

    if idletime == 0 then -- usebefore is disabled
        if usebefore then
            session.usebefore = nil
            return true
        end

        return false
    end

    usebefore = usebefore or 0

    local new_usebefore = session.now + idletime
    if new_usebefore - usebefore > 60 then
        session.usebefore = new_usebefore
        return true
    end

    return false
end

local function save(session, close)
    session.expires = session.now + session.cookie.lifetime

    set_usebefore(session)

    local cookie, err = session.strategy.save(session, close)
    if not cookie then
        return nil, err or "unable to save session cookie"
    end

    return set_cookie(session, cookie)
end

local function touch(session, close)
    if set_usebefore(session) then
        -- usebefore was updated, so set cookie
        local cookie, err = session.strategy.touch(session, close)
        if not cookie then
            return nil, err or "unable to touch session cookie"
        end

        return set_cookie(session, cookie)
    end

    if close then
        local ok, err = session.strategy.close(session)
        if not ok then
            return nil, err
        end
    end

    return true
end

local function regenerate(session, flush)
    if session.strategy.destroy then
        session.strategy.destroy(session)
    elseif session.strategy.close then
        session.strategy.close(session)
    end

    if flush then
        session.data = {}
    end

    session.id = session:identifier()
end

local secret = bytes(32, true) or bytes(32)
local defaults

local function init()
    defaults           = {
        name           = var.session_name                          or "session",
        identifier     = var.session_identifier                    or "random",
        strategy       = var.session_strategy                      or "default",
        storage        = var.session_storage                       or "cookie",
        serializer     = var.session_serializer                    or "json",
        compressor     = var.session_compressor                    or "none",
        encoder        = var.session_encoder                       or "base64",
        cipher         = var.session_cipher                        or "aes",
        hmac           = var.session_hmac                          or "sha1",
        cookie         = {
            path       = var.session_cookie_path                   or "/",
            domain     = var.session_cookie_domain,
            samesite   = var.session_cookie_samesite               or "Lax",
            secure     = enabled(var.session_cookie_secure),
            httponly   = enabled(var.session_cookie_httponly       or true),
            persistent = enabled(var.session_cookie_persistent     or false),
            discard    = tonumber(var.session_cookie_discard,  10) or 10,
            renew      = tonumber(var.session_cookie_renew,    10) or 600,
            lifetime   = tonumber(var.session_cookie_lifetime, 10) or 3600,
            idletime   = tonumber(var.session_cookie_idletime, 10) or 0,
            maxsize    = tonumber(var.session_cookie_maxsize,  10) or 4000,

        }, check       = {
            ssi        = enabled(var.session_check_ssi             or false),
            ua         = enabled(var.session_check_ua              or true),
            scheme     = enabled(var.session_check_scheme          or true),
            addr       = enabled(var.session_check_addr            or false)
        }
    }
    defaults.secret = var.session_secret or secret
end

local session = {
    _VERSION = "3.10"
}

session.__index = session

function session:get_cookie()
    return get_cookie(self)
end

function session:parse_cookie(value)
    local cookie
    local cookie_parts = COOKIE_PARTS[self.cookie.storage] or COOKIE_PARTS.DEFAULT

    local count = 1
    local pos   = 1

    local p_pos = find(value, "|", 1, true)
    while p_pos do
        if count > (cookie_parts.n - 1) then
            return nil, "too many session cookie parts"
        end
        if not cookie then
            cookie = {}
        end

        if count == 2 then
            local cookie_part = sub(value, pos, p_pos - 1)
            local c_pos = find(cookie_part, ":", 2, true)
            if c_pos then
                cookie.expires = tonumber(sub(cookie_part, 1, c_pos - 1), 10)
                if not cookie.expires then
                    return nil, "invalid session cookie expiry"
                end

                cookie.usebefore = tonumber(sub(cookie_part, c_pos + 1), 10)
                if not cookie.usebefore then
                    return nil, "invalid session cookie usebefore"
                end
            else
                cookie.expires = tonumber(cookie_part, 10)
                if not cookie.expires then
                    return nil, "invalid session cookie expiry"
                end
            end
        else
            local name = cookie_parts[count]

            local cookie_part = self.encoder.decode(sub(value, pos, p_pos - 1))
            if not cookie_part then
                return nil, "unable to decode session cookie part (" .. name .. ")"
            end

            cookie[name] = cookie_part
        end

        count = count + 1
        pos   = p_pos + 1

        p_pos = find(value, "|", pos, true)
    end

    if count ~= cookie_parts.n then
        return nil, "invalid number of session cookie parts"
    end

    local name = cookie_parts[count]

    local cookie_part = self.encoder.decode(sub(value, pos))
    if not cookie_part then
        return nil, "unable to decode session cookie part (" .. name .. ")"
    end

    cookie[name] = cookie_part

    if not cookie.id then
        return nil, "missing session cookie id"
    end

    if not cookie.expires then
        return nil, "missing session cookie expiry"
    end

    if cookie.expires <= self.now then
        return nil, "session cookie has expired"
    end

    if cookie.usebefore and cookie.usebefore <= self.now then
        return nil, "session cookie idle time has passed"
    end

    if not cookie.hash then
        return nil, "missing session cookie signature"
    end

    return cookie
end

function session.new(opts)
    if opts and getmetatable(opts) == session then
        return opts
    end

    if not defaults then
        init()
    end

    opts = type(opts) == "table" and opts or defaults

    local cookie = opts.cookie or defaults.cookie
    local name   = opts.name   or defaults.name
    local sec    = opts.secret or defaults.secret

    local secure
    local path
    local domain
    if find(name, "__Host-", 1, true) == 1 then
        secure = true
        path   = "/"
    else
        if find(name, "__Secure-", 1, true) == 1 then
            secure = true
        else
            secure = ifnil(cookie.secure, defaults.cookie.secure)
        end

        domain = cookie.domain or defaults.cookie.domain
        path   = cookie.path   or defaults.cookie.path
    end

    local check  = opts.check  or defaults.check

    local ide, iden = prequire("resty.session.identifiers.", opts.identifier or defaults.identifier, "random")
    local ser, sern = prequire("resty.session.serializers.", opts.serializer or defaults.serializer, "json")
    local com, comn = prequire("resty.session.compressors.", opts.compressor or defaults.compressor, "none")
    local enc, encn = prequire("resty.session.encoders.",    opts.encoder    or defaults.encoder,    "base64")
    local cip, cipn = prequire("resty.session.ciphers.",     opts.cipher     or defaults.cipher,     "aes")
    local sto, ston = prequire("resty.session.storage.",     opts.storage    or defaults.storage,    "cookie")
    local str, strn = prequire("resty.session.strategies.",  opts.strategy   or defaults.strategy,   "default")
    local hma, hman = prequire("resty.session.hmac.",        opts.hmac       or defaults.hmac,       "sha1")

    local self = {
        now        = time(),
        name       = name,
        secret     = sec,
        identifier = ide,
        serializer = ser,
        strategy   = str,
        encoder    = enc,
        hmac       = hma,
        cookie = {
            storage    = ston,
            encoder    = enc,
            path       = path,
            domain     = domain,
            secure     = secure,
            samesite   = cookie.samesite                  or defaults.cookie.samesite,
            httponly   = ifnil(cookie.httponly,              defaults.cookie.httponly),
            persistent = ifnil(cookie.persistent,            defaults.cookie.persistent),
            discard    = tonumber(cookie.discard,  10)    or defaults.cookie.discard,
            renew      = tonumber(cookie.renew,    10)    or defaults.cookie.renew,
            lifetime   = tonumber(cookie.lifetime, 10)    or defaults.cookie.lifetime,
            idletime   = tonumber(cookie.idletime, 10)    or defaults.cookie.idletime,
            maxsize    = tonumber(cookie.maxsize,  10)    or defaults.cookie.maxsize,
        }, check = {
            ssi        = ifnil(check.ssi,                    defaults.check.ssi),
            ua         = ifnil(check.ua,                     defaults.check.ua),
            scheme     = ifnil(check.scheme,                 defaults.check.scheme),
            addr       = ifnil(check.addr,                   defaults.check.addr),
        }
    }
    if self.cookie.idletime > 0 and self.cookie.discard > self.cookie.idletime then
        -- if using idletime, then the discard period must be less or equal
        self.cookie.discard = self.cookie.idletime
    end

    if iden and not self[iden] then self[iden] = opts[iden] end
    if sern and not self[sern] then self[sern] = opts[sern] end
    if comn and not self[comn] then self[comn] = opts[comn] end
    if encn and not self[encn] then self[encn] = opts[encn] end
    if cipn and not self[cipn] then self[cipn] = opts[cipn] end
    if ston and not self[ston] then self[ston] = opts[ston] end
    if strn and not self[strn] then self[strn] = opts[strn] end
    if hman and not self[hman] then self[hman] = opts[hman] end

    self.cipher     = cip.new(self)
    self.storage    = sto.new(self)
    self.compressor = com.new(self)

    return setmetatable(self, session)
end

function session.open(opts, keep_lock)
    local self = opts
    if self and getmetatable(self) == session then
        if self.opened then
            return self, self.present
        end
    else
        self = session.new(opts)
    end

    if self.cookie.secure == nil then
        self.cookie.secure = var.scheme == "https" or var.https == "on"
    end

    self.now = time()
    self.key = concat {
        self.check.ssi    and var.ssl_session_id  or "",
        self.check.ua     and var.http_user_agent or "",
        self.check.addr   and var.remote_addr     or "",
        self.check.scheme and var.scheme          or "",
    }

    self.opened = true

    local err
    local cookie = self:get_cookie()
    if cookie then
        cookie, err = self:parse_cookie(cookie)
        if cookie then
            local ok
            ok, err = self.strategy.open(self, cookie, keep_lock)
            if ok then
                return self, true
            end
        end
    end

    regenerate(self, true)

    return self, false, err
end

function session.start(opts)
    if opts and getmetatable(opts) == session and opts.started then
        return opts, opts.present
    end

    local self, present, reason = session.open(opts, true)

    self.started = true

    if not present then
        local ok, err = save(self)
        if not ok then
            return nil, err or "unable to save session cookie"
        end

        return self, present, reason
    end

    if self.strategy.start then
        local ok, err = self.strategy.start(self)
        if not ok then
            return nil, err or "unable to start session"
        end
    end

    if self.expires - self.now < self.cookie.renew
    or self.expires > self.now + self.cookie.lifetime
    then
        local ok, err = save(self)
        if not ok then
            return nil, err or "unable to save session cookie"
        end
    else
        -- we're not saving, so we must touch to update idletime/usebefore
        local ok, err = touch(self)
        if not ok then
            return nil, err or "unable to touch session cookie"
        end
    end

    return self, true
end

function session.destroy(opts)
    if opts and getmetatable(opts) == session and opts.destroyed then
        return true
    end

    local self, err = session.start(opts)
    if not self then
        return nil, err
    end

    if self.strategy.destroy then
        self.strategy.destroy(self)
    elseif self.strategy.close then
        self.strategy.close(self)
    end

    self.data      = {}
    self.present   = nil
    self.opened    = nil
    self.started   = nil
    self.closed    = true
    self.destroyed = true

    return set_cookie(self, "", true)
end

function session:regenerate(flush, close)
    close = close ~= false
    if self.strategy.regenerate then
        if flush then
            self.data = {}
        end

        if not self.id then
            self.id = session:identifier()
        end
    else
        regenerate(self, flush)
    end

    return save(self, close)
end

function session:save(close)
    close = close ~= false

    if not self.id then
        self.id = self:identifier()
    end

    return save(self, close)
end

function session:close()
    self.closed = true

    if self.strategy.close then
        return self.strategy.close(self)
    end

    return true
end

function session:hide()
    local cookies = var.http_cookie
    if not cookies or cookies == "" then
        return
    end

    local results = {}
    local name = self.name
    local name_len = #name
    local found
    local i = 1
    local j = 0
    local sc_pos = find(cookies, ";", i, true)
    while sc_pos do
        local isc, cookie = is_session_cookie(sub(cookies, i, sc_pos - 1), name, name_len)
        if isc then
            found = true
        elseif cookie then
            j = j + 1
            results[j] = cookie
        end

        i = sc_pos + 1
        sc_pos = find(cookies, ";", i, true)
    end

    local isc, cookie
    if i == 1 then
        isc, cookie = is_session_cookie(cookies, name, name_len)
    else
        isc, cookie = is_session_cookie(sub(cookies, i), name, name_len)
    end

    if not isc and cookie then
        if not found then
            return
        end

        j = j + 1
        results[j] = cookie
    end

    if j == 0 then
        clear_header("Cookie")
    else
        set_header("Cookie", concat(results, "; ", 1, j))
    end
end

return session
