-- Copyright (C) Yichun Zhang (agentzh)


-- local sub = string.sub
local req_socket = ngx.req.socket
local match = string.match
local setmetatable = setmetatable
local type = type
local ngx_var = ngx.var
local ngx_init_body = ngx.req.init_body
local ngx_finish_body = ngx.req.finish_body
local ngx_append_body = ngx.req.append_body
-- local print = print


local _M = { _VERSION = '0.11' }


local CHUNK_SIZE = 4096
local MAX_LINE_SIZE = 512

local STATE_BEGIN = 1
local STATE_READING_HEADER = 2
local STATE_READING_BODY = 3
local STATE_EOF = 4

local mt = { __index = _M }

local state_handlers

local function wrapped_receiveuntil(self, until_str)
    local iter, err_outer = self:old_receiveuntil(until_str)
    if iter == nil then
        ngx_finish_body()
    end

    local function wrapped(size)
        local ret, err = iter(size)
        if ret then
            ngx_append_body(ret)
        end

        -- non-nil ret for call with no size or successful size call and nil ret
        if (not size and ret) or (size and not ret and not err) then
            ngx_append_body(until_str)
        end
        return ret, err
    end

    return wrapped, err_outer
end


local function wrapped_receive(self, arg)
    local ret, err, partial = self:old_receive(arg)
    if ret then
        ngx_append_body(ret)

    elseif partial then
        ngx_append_body(partial)
    end

    if ret == nil then
        ngx_finish_body()
    end

    return ret, err
end


local function req_socket_body_collector(sock)
    sock.old_receiveuntil = sock.receiveuntil
    sock.old_receive = sock.receive
    sock.receiveuntil = wrapped_receiveuntil
    sock.receive = wrapped_receive
end


local function get_boundary()
    local header = ngx_var.content_type
    if not header then
        return nil
    end

    if type(header) == "table" then
        header = header[1]
    end

    local m = match(header, ";%s*boundary=\"([^\"]+)\"")
    if m then
        return m
    end

    return match(header, ";%s*boundary=([^\",;]+)")
end


function _M.new(self, chunk_size, max_line_size, preserve_body)
    local boundary = get_boundary()

    -- print("boundary: ", boundary)

    if not boundary then
        return nil, "no boundary defined in Content-Type"
    end

    -- print('boundary: "', boundary, '"')

    local sock, err = req_socket()
    if not sock then
        return nil, err
    end

    if preserve_body then
        ngx_init_body(chunk_size)
        req_socket_body_collector(sock)
    end

    local read2boundary, err = sock:receiveuntil("--" .. boundary)
    if not read2boundary then
        return nil, err
    end

    local read_line, err = sock:receiveuntil("\r\n")
    if not read_line then
        return nil, err
    end

    return setmetatable({
        sock = sock,
        size = chunk_size or CHUNK_SIZE,
        line_size = max_line_size or MAX_LINE_SIZE,
        read2boundary = read2boundary,
        read_line = read_line,
        boundary = boundary,
        state = STATE_BEGIN,
        preserve_body = preserve_body
    }, mt)
end


function _M.set_timeout(self, timeout)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    return sock:settimeout(timeout)
end


local function discard_line(self)
    local read_line = self.read_line

    local line, err = read_line(self.line_size)
    if not line then
        return nil, err
    end

    local dummy, err = read_line(1)
    if dummy then
        if self.preserve_body then
            ngx_finish_body()
        end

        return nil, "line too long: " .. line .. dummy .. "..."
    end

    if err then
        return nil, err
    end

    return 1
end


local function discard_rest(self)
    local sock = self.sock
    local size = self.size

    while true do
        local dummy, err = sock:receive(size)
        if err and err ~= 'closed' then
            return nil, err
        end

        if not dummy then
            return 1
        end
    end
end


local function read_body_part(self)
    local read2boundary = self.read2boundary

    local chunk, err = read2boundary(self.size)
    if err then
        return nil, nil, err
    end

    if not chunk then
        local sock = self.sock

        local data = sock:receive(2)
        if data == "--" then
            local ok, err = discard_rest(self)
            if not ok then
                return nil, nil, err
            end

            self.state = STATE_EOF
            return "part_end"
        end

        if data ~= "\r\n" then
            local ok, err = discard_line(self)
            if not ok then
                return nil, nil, err
            end
        end

        self.state = STATE_READING_HEADER
        return "part_end"
    end

    return "body", chunk
end


local function read_header(self)
    local read_line = self.read_line

    local line, err = read_line(self.line_size)
    if err then
        return nil, nil, err
    end

    local dummy, err = read_line(1)
    if dummy then
        if self.preserve_body then
            ngx_finish_body()
        end
 
        return nil, nil, "line too long: " .. line .. dummy .. "..."
    end

    if err then
        return nil, nil, err
    end

    -- print("read line: ", line)

    if line == "" then
        -- after the last header
        self.state = STATE_READING_BODY
        return read_body_part(self)
    end

    local key, value = match(line, "([^: \t]+)%s*:%s*(.+)")
    if not key then
        return 'header', line
    end

    return 'header', {key, value, line}
end


local function eof()
    return "eof", nil
end


function _M.read(self)
    -- local size = self.size

    local handler = state_handlers[self.state]
    if handler then
        return handler(self)
    end

    return nil, nil, "bad state: " .. self.state
end


local function read_preamble(self)
    local sock = self.sock
    if not sock then
        return nil, nil, "not initialized"
    end

    local size = self.size
    local read2boundary = self.read2boundary

    while true do
        local preamble = read2boundary(size)
        if not preamble then
            break
        end

        -- discard the preamble data chunk
        -- print("read preamble: ", preamble)
    end

    local ok, err = discard_line(self)
    if not ok then
        return nil, nil, err
    end

    local read2boundary, err = sock:receiveuntil("\r\n--" .. self.boundary)
    if not read2boundary then
        return nil, nil, err
    end

    self.read2boundary = read2boundary

    self.state = STATE_READING_HEADER
    return read_header(self)
end


state_handlers = {
    read_preamble,
    read_header,
    read_body_part,
    eof
}


return _M
