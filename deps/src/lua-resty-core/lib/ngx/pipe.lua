-- Copyright (C) by OpenResty Inc.


local base = require "resty.core.base"
base.allows_subsystem("http")


require "resty.core.phase"  -- for ngx.get_phase

local assert = assert
local error = error
local ipairs = ipairs
local tonumber = tonumber
local tostring = tostring
local type = type
local str_find = string.find
local table_concat = table.concat
local ffi = require "ffi"
local C = ffi.C
local ffi_new = ffi.new
local ffi_str = ffi.string
local ngx_phase = ngx.get_phase
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr
local get_request = base.get_request
local FFI_AGAIN = base.FFI_AGAIN
local FFI_BAD_CONTEXT = base.FFI_BAD_CONTEXT
local FFI_DECLINED = base.FFI_DECLINED
local FFI_ERROR = base.FFI_ERROR
local FFI_NO_REQ_CTX = base.FFI_NO_REQ_CTX
local FFI_OK = base.FFI_OK
local co_yield = coroutine._yield


ffi.cdef[[
typedef int                         ngx_pid_t;
typedef uintptr_t                   ngx_msec_t;
typedef unsigned char               u_char;
typedef struct ngx_http_lua_pipe_s  ngx_http_lua_pipe_t;

typedef struct {
    ngx_pid_t               _pid;
    ngx_msec_t              write_timeout;
    ngx_msec_t              stdout_read_timeout;
    ngx_msec_t              stderr_read_timeout;
    ngx_msec_t              wait_timeout;
    ngx_http_lua_pipe_t    *pipe;
} ngx_http_lua_ffi_pipe_proc_t;

int ngx_http_lua_ffi_pipe_spawn(ngx_http_lua_ffi_pipe_proc_t *proc,
    const char *file, const char **argv, int merge_stderr, size_t buffer_size,
    const char **environ, u_char *errbuf, size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_proc_read(ngx_http_request_t *r,
    ngx_http_lua_ffi_pipe_proc_t *proc, int from_stderr, int reader_type,
    size_t length, u_char **buf, size_t *buf_size, u_char *errbuf,
    size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_get_read_result(ngx_http_request_t *r,
    ngx_http_lua_ffi_pipe_proc_t *proc, int from_stderr, u_char **buf,
    size_t *buf_size, u_char *errbuf, size_t *errbuf_size);

ssize_t ngx_http_lua_ffi_pipe_proc_write(ngx_http_request_t *r,
    ngx_http_lua_ffi_pipe_proc_t *proc, const u_char *data, size_t len,
    u_char *errbuf, size_t *errbuf_size);

ssize_t ngx_http_lua_ffi_pipe_get_write_result(ngx_http_request_t *r,
    ngx_http_lua_ffi_pipe_proc_t *proc, u_char *errbuf, size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_proc_shutdown_stdin(
    ngx_http_lua_ffi_pipe_proc_t *proc, u_char *errbuf, size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_proc_shutdown_stdout(
    ngx_http_lua_ffi_pipe_proc_t *proc, u_char *errbuf, size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_proc_shutdown_stderr(
    ngx_http_lua_ffi_pipe_proc_t *proc, u_char *errbuf, size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_proc_wait(ngx_http_request_t *r,
    ngx_http_lua_ffi_pipe_proc_t *proc, char **reason, int *status,
    u_char *errbuf, size_t *errbuf_size);

int ngx_http_lua_ffi_pipe_proc_kill(ngx_http_lua_ffi_pipe_proc_t *proc,
    int signal, u_char *errbuf, size_t *errbuf_size);

void ngx_http_lua_ffi_pipe_proc_destroy(ngx_http_lua_ffi_pipe_proc_t *proc);
]]


if not pcall(function() return C.ngx_http_lua_ffi_pipe_spawn end) then
    error("pipe API is not supported due to either a platform issue " ..
          "or lack of the HAVE_SOCKET_CLOEXEC_PATCH patch", 2)
end


local _M = { version = base.version }


local ERR_BUF_SIZE = 256
local VALUE_BUF_SIZE = 512
local PIPE_READ_ALL   = 0
local PIPE_READ_BYTES = 1
local PIPE_READ_LINE  = 2
local PIPE_READ_ANY   = 3


local proc_set_timeouts
do
    local MAX_TIMEOUT = 0xffffffff

    function proc_set_timeouts(proc, write_timeout, stdout_read_timeout,
                               stderr_read_timeout, wait_timeout)

        -- the implementation below is straightforward but could not be JIT
        -- compiled by the latest LuaJIT. When called in loops, LuaJIT will try
        -- to unroll it, and fall back to interpreter after it reaches the
        -- unroll limit.
        --[[
        local function set_timeout(proc, attr, timeout)
            if timeout then
                if timeout > MAX_TIMEOUT then
                    error("bad timeout value", 3)
                end
                proc[attr] = timeout
            end
        end
        set_timeout(...)
        ]]

        if write_timeout then
            if write_timeout < 0 or MAX_TIMEOUT < write_timeout then
                error("bad write_timeout option", 3)
            end

            proc.write_timeout = write_timeout
        end

        if stdout_read_timeout then
            if stdout_read_timeout < 0 or MAX_TIMEOUT < stdout_read_timeout then
                error("bad stdout_read_timeout option", 3)
            end

            proc.stdout_read_timeout = stdout_read_timeout
        end

        if stderr_read_timeout then
            if stderr_read_timeout < 0 or MAX_TIMEOUT < stderr_read_timeout then
                error("bad stderr_read_timeout option", 3)
            end

            proc.stderr_read_timeout = stderr_read_timeout
        end

        if wait_timeout then
            if wait_timeout < 0 or MAX_TIMEOUT < wait_timeout then
                error("bad wait_timeout option", 3)
            end

            proc.wait_timeout = wait_timeout
        end
    end
end


local function check_proc_instance(proc)
    if type(proc) ~= "cdata" then
        error("not a process instance", 3)
    end
end


local proc_read
do
    local value_buf = ffi_new("char[?]", VALUE_BUF_SIZE)
    local buf = ffi_new("char *[1]")
    local buf_size = ffi_new("size_t[1]")

    function proc_read(proc, stderr, reader_type, len)
        check_proc_instance(proc)

        local r = get_request()
        if not r then
            error("no request found")
        end

        buf[0] = value_buf
        buf_size[0] = VALUE_BUF_SIZE
        local errbuf = get_string_buf(ERR_BUF_SIZE)
        local errbuf_size = get_size_ptr()
        errbuf_size[0] = ERR_BUF_SIZE
        local rc = C.ngx_http_lua_ffi_pipe_proc_read(r, proc, stderr,
                                                     reader_type, len, buf,
                                                     buf_size, errbuf,
                                                     errbuf_size)
        if rc == FFI_NO_REQ_CTX then
            error("no request ctx found")
        end

        if rc == FFI_BAD_CONTEXT then
            error(ffi_str(errbuf, errbuf_size[0]), 2)
        end

        while true do
            if rc == FFI_ERROR then
                return nil, ffi_str(errbuf, errbuf_size[0])
            end

            if rc == FFI_OK then
                local p = buf[0]
                if p ~= value_buf then
                    p = ffi_new("char[?]", buf_size[0])
                    buf[0] = p
                    C.ngx_http_lua_ffi_pipe_get_read_result(r, proc, stderr,
                                                            buf, buf_size,
                                                            errbuf, errbuf_size)
                    assert(p == buf[0])
                end

                return ffi_str(p, buf_size[0])
            end

            if rc == FFI_DECLINED then
                local err = ffi_str(errbuf, errbuf_size[0])

                local p = buf[0]
                if p ~= value_buf then
                    p = ffi_new("char[?]", buf_size[0])
                    buf[0] = p
                    C.ngx_http_lua_ffi_pipe_get_read_result(r, proc, stderr,
                                                            buf, buf_size,
                                                            errbuf, errbuf_size)
                    assert(p == buf[0])
                end

                local partial = ffi_str(p, buf_size[0])
                return nil, err, partial
            end

            assert(rc == FFI_AGAIN)

            co_yield()

            buf[0] = value_buf
            buf_size[0] = VALUE_BUF_SIZE
            errbuf = get_string_buf(ERR_BUF_SIZE)
            errbuf_size = get_size_ptr()
            errbuf_size[0] = ERR_BUF_SIZE
            rc = C.ngx_http_lua_ffi_pipe_get_read_result(r, proc, stderr, buf,
                                                         buf_size, errbuf,
                                                         errbuf_size)
        end
    end

end


local function proc_write(proc, data)
    check_proc_instance(proc)

    local r = get_request()
    if not r then
        error("no request found", 2)
    end

    local data_type = type(data)
    if data_type ~= "string" then
        if data_type == "table" then
            data = table_concat(data, "")

        elseif data_type == "number" then
            data = tostring(data)

        else
            error("bad data arg: string, number, or table expected, got "
                  .. data_type, 2)
        end
    end

    local errbuf = get_string_buf(ERR_BUF_SIZE)
    local errbuf_size = get_size_ptr()
    errbuf_size[0] = ERR_BUF_SIZE
    local rc = C.ngx_http_lua_ffi_pipe_proc_write(r, proc, data, #data, errbuf,
                                                  errbuf_size)
    if rc == FFI_NO_REQ_CTX then
        error("no request ctx found", 2)
    end

    if rc == FFI_BAD_CONTEXT then
        error(ffi_str(errbuf, errbuf_size[0]), 2)
    end

    while true do
        if rc == FFI_ERROR then
            return nil, ffi_str(errbuf, errbuf_size[0])
        end

        if rc >= 0 then
            -- rc holds the bytes sent
            return tonumber(rc)
        end

        assert(rc == FFI_AGAIN)

        co_yield()

        errbuf = get_string_buf(ERR_BUF_SIZE)
        errbuf_size = get_size_ptr()
        errbuf_size[0] = ERR_BUF_SIZE
        rc = C.ngx_http_lua_ffi_pipe_get_write_result(r, proc, errbuf,
                                                      errbuf_size)
    end
end


local function proc_shutdown(proc, direction)
    check_proc_instance(proc)

    local rc
    local errbuf = get_string_buf(ERR_BUF_SIZE)
    local errbuf_size = get_size_ptr()
    errbuf_size[0] = ERR_BUF_SIZE

    if direction == "stdin" then
        rc = C.ngx_http_lua_ffi_pipe_proc_shutdown_stdin(proc, errbuf,
                                                         errbuf_size)

    elseif direction == "stdout" then
        rc = C.ngx_http_lua_ffi_pipe_proc_shutdown_stdout(proc, errbuf,
                                                          errbuf_size)

    elseif direction == "stderr" then
        rc = C.ngx_http_lua_ffi_pipe_proc_shutdown_stderr(proc, errbuf,
                                                          errbuf_size)

    else
        error("bad shutdown arg: " .. direction, 2)
    end

    if rc == FFI_ERROR then
        return nil, ffi_str(errbuf, errbuf_size[0])
    end

    return true
end


local proc_wait
do
    local reason = ffi_new("char *[1]")
    local status = ffi_new("int[1]")

    function proc_wait(proc)
        check_proc_instance(proc)

        local r = get_request()
        if not r then
            error("no request found", 2)
        end

        local errbuf = get_string_buf(ERR_BUF_SIZE)
        local errbuf_size = get_size_ptr()
        errbuf_size[0] = ERR_BUF_SIZE
        local rc = C.ngx_http_lua_ffi_pipe_proc_wait(r, proc, reason, status,
                                                     errbuf, errbuf_size)
        if rc == FFI_NO_REQ_CTX then
            error("no request ctx found", 2)
        end

        if rc == FFI_BAD_CONTEXT then
            error(ffi_str(errbuf, errbuf_size[0]), 2)
        end

        if rc == FFI_ERROR then
            return nil, ffi_str(errbuf, errbuf_size[0])
        end

        if rc == FFI_OK then
            return true, ffi_str(reason[0]), tonumber(status[0])
        end

        if rc == FFI_DECLINED then
            return false, ffi_str(reason[0]), tonumber(status[0])
        end

        local ok, exit_reason, exit_status
        ok, exit_reason, exit_status = co_yield()
        return ok, exit_reason, exit_status
    end
end


local function proc_kill(proc, signal)
    check_proc_instance(proc)

    if type(signal) ~= "number" then
        error("bad signal arg: number expected, got " .. tostring(signal), 2)
    end

    local errbuf = get_string_buf(ERR_BUF_SIZE)
    local errbuf_size = get_size_ptr()
    errbuf_size[0] = ERR_BUF_SIZE

    local rc = C.ngx_http_lua_ffi_pipe_proc_kill(proc, signal, errbuf,
                                                 errbuf_size)
    if rc == FFI_ERROR then
        return nil, ffi_str(errbuf, errbuf_size[0])
    end

    return true
end


local mt = {
    __gc = C.ngx_http_lua_ffi_pipe_proc_destroy,

    __index = {
        pid = function (proc)
            return proc._pid
        end,

        set_timeouts = function (proc, write_timeout, stdout_read_timeout,
                                 stderr_read_timeout, wait_timeout)
            proc_set_timeouts(proc, write_timeout, stdout_read_timeout,
                              stderr_read_timeout, wait_timeout)
        end,

        stdout_read_all = function (proc)
            local data, err, partial = proc_read(proc, 0, PIPE_READ_ALL, 0)
            return data, err, partial
        end,

        stdout_read_bytes = function (proc, len)
            if len <= 0 then
                if len < 0 then
                    error("bad len argument", 2)
                end

                return ""
            end

            local data, err, partial = proc_read(proc, 0, PIPE_READ_BYTES, len)
            return data, err, partial
        end,

        stdout_read_line = function (proc)
            local data, err, partial = proc_read(proc, 0, PIPE_READ_LINE, 0)
            return data, err, partial
        end,

        stdout_read_any = function (proc, max)
            if type(max) ~= "number" then
                max = tonumber(max)
            end

            if not max or max <= 0 then
                error("bad max argument", 2)
            end

            local data, err, partial = proc_read(proc, 0, PIPE_READ_ANY, max)
            return data, err, partial
        end,

        stderr_read_all = function (proc)
            local data, err, partial = proc_read(proc, 1, PIPE_READ_ALL, 0)
            return data, err, partial
        end,

        stderr_read_bytes = function (proc, len)
            if len <= 0 then
                if len < 0 then
                    error("bad len argument", 2)
                end

                return ""
            end

            local data, err, partial = proc_read(proc, 1, PIPE_READ_BYTES, len)
            return data, err, partial
        end,

        stderr_read_line = function (proc)
            local data, err, partial = proc_read(proc, 1, PIPE_READ_LINE, 0)
            return data, err, partial
        end,

        stderr_read_any = function (proc, max)
            if type(max) ~= "number" then
                max = tonumber(max)
            end

            if not max or max <= 0 then
                error("bad max argument", 2)
            end

            local data, err, partial = proc_read(proc, 1, PIPE_READ_ANY, max)
            return data, err, partial
        end,

        write = proc_write,
        shutdown = proc_shutdown,
        wait = proc_wait,
        kill = proc_kill,
    }
}
local Proc = ffi.metatype("ngx_http_lua_ffi_pipe_proc_t", mt)


local pipe_spawn
do
    local sh_exe = "/bin/sh"
    local opt_c = "-c"
    local shell_args = ffi_new("const char* [?]", 4)
    shell_args[0] = sh_exe
    shell_args[1] = opt_c
    shell_args[3] = nil

    local write_timeout = 10000
    local stdout_read_timeout = 10000
    local stderr_read_timeout = 10000
    local wait_timeout = 10000

    -- reference shell cmd's constant strings here to prevent them from getting
    -- collected by the Lua GC.
    _M._gc_ref_c_opt = opt_c

    function pipe_spawn(args, opts)
        if ngx_phase() == "init" then
            error("API disabled in the current context", 2)
        end

        local exe
        local proc_args
        local proc_envs

        local args_type = type(args)
        if args_type == "table" then
            local nargs = 0

            for i, arg in ipairs(args)  do
                nargs = nargs + 1

                if type(arg) ~= "string" then
                    args[i] = tostring(arg)
                end
            end

            if nargs == 0 then
                error("bad args arg: non-empty table expected", 2)
            end

            exe = args[1]
            proc_args = ffi_new("const char* [?]", nargs + 1, args)
            proc_args[nargs] = nil

        elseif args_type == "string" then
            exe = sh_exe
            shell_args[2] = args
            proc_args = shell_args

        else
            error("bad args arg: table expected, got " .. args_type, 2)
        end

        local merge_stderr = 0
        local buffer_size = 4096
        local proc = Proc()

        if opts then
            merge_stderr = opts.merge_stderr and 1 or 0

            if opts.buffer_size then
                buffer_size = tonumber(opts.buffer_size)

                if not buffer_size or buffer_size < 1 then
                    error("bad buffer_size option", 2)
                end
            end

            if opts.environ then
                local environ = opts.environ
                local environ_type = type(environ)
                if environ_type ~= "table" then
                    error("bad environ option: table expected, got " ..
                          environ_type, 2)
                end

                local nenv = 0

                for i, env in ipairs(environ) do
                    nenv = nenv + 1

                    local env_type = type(env)
                    if env_type ~= "string" then
                        error("bad value at index " .. i .. " of environ " ..
                              "option: string expected, got " .. env_type, 2)
                    end

                    if not str_find(env, "=", 2, true) then
                        error("bad value at index " .. i .. " of environ " ..
                              "option: 'name=[value]' format expected, got '" ..
                              env .. "'", 2)
                    end
                end

                if nenv > 0 then
                    proc_envs = ffi_new("const char* [?]", nenv + 1, environ)
                    proc_envs[nenv] = nil
                end
            end

            proc_set_timeouts(proc,
                              opts.write_timeout or write_timeout,
                              opts.stdout_read_timeout or stdout_read_timeout,
                              opts.stderr_read_timeout or stderr_read_timeout,
                              opts.wait_timeout or wait_timeout)

        else
            proc_set_timeouts(proc,
                              write_timeout,
                              stdout_read_timeout,
                              stderr_read_timeout,
                              wait_timeout)
        end

        local errbuf = get_string_buf(ERR_BUF_SIZE)
        local errbuf_size = get_size_ptr()
        errbuf_size[0] = ERR_BUF_SIZE
        local rc = C.ngx_http_lua_ffi_pipe_spawn(proc, exe, proc_args,
                                                 merge_stderr, buffer_size,
                                                 proc_envs, errbuf, errbuf_size)
        if rc == FFI_ERROR then
            return nil, ffi_str(errbuf, errbuf_size[0])
        end

        return proc
    end
end  -- do


_M.spawn = pipe_spawn


return _M
