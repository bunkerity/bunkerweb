-- I hereby assign copyright in this code to the lua-resty-core project,
-- to be licensed under the same terms as the rest of the code.


local base = require "resty.core.base"
local ffi = require 'ffi'
local bit = require "bit"
local core_regex = require "resty.core.regex"


if core_regex.no_pcre then
    error("no support for 'ngx.re' module: OpenResty was " ..
          "compiled without PCRE support", 3)
end


local C = ffi.C
local ffi_str = ffi.string
local sub = string.sub
local error = error
local type = type
local band = bit.band
local new_tab = base.new_tab
local tostring = tostring
local math_max = math.max
local math_min = math.min
local is_regex_cache_empty = core_regex.is_regex_cache_empty
local re_match_compile = core_regex.re_match_compile
local destroy_compiled_regex = core_regex.destroy_compiled_regex
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr
local FFI_OK = base.FFI_OK
local subsystem = ngx.config.subsystem


local MAX_ERR_MSG_LEN        = 128
local FLAG_DFA               = 0x02
local PCRE_ERROR_NOMATCH     = -1
local DEFAULT_SPLIT_RES_SIZE = 4


local split_ctx = new_tab(0, 1)
local ngx_lua_ffi_set_jit_stack_size
local ngx_lua_ffi_exec_regex


if subsystem == 'http' then
    ffi.cdef[[
int ngx_http_lua_ffi_set_jit_stack_size(int size, unsigned char *errstr,
    size_t *errstr_size);
    ]]

    ngx_lua_ffi_exec_regex = C.ngx_http_lua_ffi_exec_regex
    ngx_lua_ffi_set_jit_stack_size = C.ngx_http_lua_ffi_set_jit_stack_size

elseif subsystem == 'stream' then
    ffi.cdef[[
int ngx_stream_lua_ffi_set_jit_stack_size(int size, unsigned char *errstr,
    size_t *errstr_size);
    ]]

    ngx_lua_ffi_exec_regex = C.ngx_stream_lua_ffi_exec_regex
    ngx_lua_ffi_set_jit_stack_size = C.ngx_stream_lua_ffi_set_jit_stack_size
end


local _M = { version = base.version }


local function re_split_helper(subj, compiled, compile_once, flags, ctx)
    local rc
    do
        local pos = math_max(ctx.pos, 0)

        rc = ngx_lua_ffi_exec_regex(compiled, flags, subj, #subj, pos)
    end

    if rc == PCRE_ERROR_NOMATCH then
        return nil, nil, nil
    end

    if rc < 0 then
        if not compile_once then
            destroy_compiled_regex(compiled)
        end
        return nil, nil, nil, "pcre_exec() failed: " .. rc
    end

    if rc == 0 then
        if band(flags, FLAG_DFA) == 0 then
            if not compile_once then
                destroy_compiled_regex(compiled)
            end
            return nil, nil, nil, "capture size too small"
        end

        rc = 1
    end

    local caps = compiled.captures
    local ncaps = compiled.ncaptures

    local from = caps[0]
    local to = caps[1]

    if from < 0 or to < 0 then
        return nil, nil, nil
    end

    if from == to then
        -- empty match, skip to next char
        ctx.pos = to + 1

    else
        ctx.pos = to
    end

    -- convert to Lua string indexes

    from = from + 1
    to = to + 1

    -- retrieve the first sub-match capture if any

    if ncaps > 0 and rc > 1 then
        return from, to, sub(subj, caps[2] + 1, caps[3])
    end

    return from, to
end


function _M.split(subj, regex, opts, ctx, max, res)
    -- we need to cast this to strings to avoid exceptions when they are
    -- something else.
    -- needed because of further calls to string.sub in this function.
    subj = tostring(subj)

    if not ctx then
        ctx = split_ctx
        ctx.pos = 1 -- set or reset upvalue field

    elseif not ctx.pos then
        -- ctx provided by user but missing pos field
        ctx.pos = 1
    end

    max = max or 0

    if not res then
        -- limit the initial arr_n size of res to a reasonable value
        -- 0 < narr <= DEFAULT_SPLIT_RES_SIZE
        local narr = DEFAULT_SPLIT_RES_SIZE
        if max > 0 then
            -- the user specified a valid max limiter if max > 0
            narr = math_min(narr, max)
        end

        res = new_tab(narr, 0)

    elseif type(res) ~= "table" then
        error("res is not a table", 2)
    end

    local len = #subj
    if ctx.pos > len then
        res[1] = nil
        return res
    end

    -- compile regex

    local compiled, compile_once, flags = re_match_compile(regex, opts)
    if compiled == nil then
        -- compiled_once holds the error string
        return nil, compile_once
    end

    local sub_idx = ctx.pos
    local res_idx = 0
    local last_empty_match

    -- update to split_helper PCRE indexes
    ctx.pos = sub_idx - 1

    -- splitting: with and without a max limiter

    if max > 0 then
        local count = 1

        while count < max do
            local from, to, capture, err = re_split_helper(subj, compiled,
                                                compile_once, flags, ctx)
            if err then
                return nil, err
            end

            if not from then
                break
            end

            if last_empty_match then
                sub_idx = last_empty_match
            end

            if from == to then
                last_empty_match = from
            end

            if from > sub_idx or not last_empty_match then
                count = count + 1
                res_idx = res_idx + 1
                res[res_idx] = sub(subj, sub_idx, from - 1)

                if capture then
                    res_idx = res_idx + 1
                    res[res_idx] = capture
                end

                sub_idx = to

                if sub_idx > len then
                    break
                end
            end
        end

    else
        while true do
            local from, to, capture, err = re_split_helper(subj, compiled,
                                                compile_once, flags, ctx)
            if err then
                return nil, err
            end

            if not from then
                break
            end

            if last_empty_match then
                sub_idx = last_empty_match
            end

            if from == to then
                last_empty_match = from
            end

            if from > sub_idx or not last_empty_match then
                res_idx = res_idx + 1
                res[res_idx] = sub(subj, sub_idx, from - 1)

                if capture then
                    res_idx = res_idx + 1
                    res[res_idx] = capture
                end

                sub_idx = to

                if sub_idx > len then
                    break
                end
            end
        end

    end

    if not compile_once then
        destroy_compiled_regex(compiled)
    end

    -- trailing nil for non-cleared res tables

    -- delete empty trailing ones (without max)
    if max <= 0 and sub_idx > len then
        for ety_idx = res_idx, 1, -1 do
            if res[ety_idx] ~= "" then
                res_idx = ety_idx
                break
            end

            res[ety_idx] = nil
        end
    else
        res_idx = res_idx + 1
        res[res_idx] = sub(subj, sub_idx)
    end

    res[res_idx + 1] = nil

    return res
end


function _M.opt(option, value)
    if option == "jit_stack_size" then
        if not is_regex_cache_empty() then
            error("changing jit stack size is not allowed when some " ..
                  "regexs have already been compiled and cached", 2)
        end

        local errbuf = get_string_buf(MAX_ERR_MSG_LEN)
        local sizep = get_size_ptr()
        sizep[0] = MAX_ERR_MSG_LEN

        local rc = ngx_lua_ffi_set_jit_stack_size(value, errbuf, sizep)

        if rc == FFI_OK then
            return
        end

        error(ffi_str(errbuf, sizep[0]), 2)
    end

    error("unrecognized option name", 2)
end


return _M
