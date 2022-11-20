local ltn12 = require("ltn12")

dofile("testsupport.lua")

local function format(chunk)
    if chunk then
        if chunk == "" then return "''"
        else return string.len(chunk) end
    else return "nil" end
end

local function show(name, input, output)
    local sin = format(input)
    local sout = format(output)
    io.write(name, ": ", sin, " -> ", sout, "\n")
end

local function chunked(length)
    local tmp
    return function(chunk)
        local ret
        if chunk and chunk ~= "" then
            tmp = chunk
        end
        ret = string.sub(tmp, 1, length)
        tmp = string.sub(tmp, length+1)
        if not chunk and ret == "" then ret = nil end
        return ret
    end
end

local function named(f, name)
    return function(chunk)
        local ret = f(chunk)
        show(name, chunk, ret)
        return ret
    end
end

--------------------------------
local function split(size)
    local buffer = ""
    local last_out = ""
    local last_in = ""
    local function output(chunk)
        local part = string.sub(buffer, 1, size)
        buffer = string.sub(buffer, size+1)
        last_out = (part ~= "" or chunk) and part
        last_in = chunk
        return last_out
    end
    return function(chunk, done)
        if done then
            return not last_in and not last_out
        end
        -- check if argument is consistent with state
        if not chunk then
            if last_in and last_in ~= "" and last_out ~= "" then
                error("nil chunk following data chunk", 2)
            end
            if not last_out then error("extra nil chunk", 2) end
            return output(chunk)
        elseif chunk == "" then
            if last_out == "" then error('extra "" chunk', 2) end
            if not last_out then error('"" chunk following nil return', 2) end
            if not last_in then error('"" chunk following nil chunk', 2) end
            return output(chunk)
        else
            if not last_in  then error("data chunk following nil chunk", 2) end
            if last_in ~= "" and last_out ~= "" then
                error("data chunk following data chunk", 2)
            end
            buffer = chunk
            return output(chunk)
        end
    end
end

--------------------------------
local function format(chunk)
    if chunk then
        if chunk == "" then return "''"
        else return string.len(chunk) end
    else return "nil" end
end

--------------------------------
local function merge(size)
    local buffer = ""
    local last_out = ""
    local last_in = ""
    local function output(chunk)
        local part
        if string.len(buffer) >= size or not chunk then
            part = buffer
            buffer = ""
        else
            part = ""
        end
        last_out = (part ~= "" or chunk) and part
        last_in = chunk
        return last_out
    end
    return function(chunk, done)
        if done then
            return not last_in and not last_out
        end
        -- check if argument is consistent with state
        if not chunk then
            if last_in and last_in ~= "" and last_out ~= "" then
                error("nil chunk following data chunk", 2)
            end
            if not last_out then error("extra nil chunk", 2) end
            return output(chunk)
        elseif chunk == "" then
            if last_out == "" then error('extra "" chunk', 2) end
            if not last_out then error('"" chunk following nil return', 2) end
            if not last_in then error('"" chunk following nil chunk', 2) end
            return output(chunk)
        else
            if not last_in  then error("data chunk following nil chunk", 2) end
            if last_in ~= "" and last_out ~= "" then
                error("data chunk following data chunk", 2)
            end
            buffer = buffer .. chunk
            return output(chunk)
        end
    end
end

--------------------------------
io.write("testing sink.table: ")
local sink, t = ltn12.sink.table()
local s, c = "", ""
for i = 0, 10 do
    c = string.rep(string.char(i), i)
    s = s .. c
    assert(sink(c), "returned error")
end
assert(sink(nil), "returned error")
assert(table.concat(t) == s, "mismatch")
print("ok")

--------------------------------
io.write("testing sink.chain (with split): ")
sink, t = ltn12.sink.table()
local filter = split(3)
sink = ltn12.sink.chain(filter, sink)
s = "123456789012345678901234567890"
assert(sink(s), "returned error")
assert(sink(s), "returned error")
assert(sink(nil), "returned error")
assert(table.concat(t) == s .. s, "mismatch")
assert(filter(nil, 1), "filter not empty")
print("ok")

--------------------------------
io.write("testing sink.chain (with merge): ")
sink, t = ltn12.sink.table()
filter = merge(10)
sink = ltn12.sink.chain(filter, sink)
s = string.rep("123", 30)
s = s .. string.rep("4321", 30)
for i = 1, 30 do
    assert(sink("123"), "returned error")
end
for i = 1, 30 do
    assert(sink("4321"), "returned error")
end
assert(sink(nil), "returned error")
assert(filter(nil, 1), "filter not empty")
assert(table.concat(t) == s, "mismatch")
print("ok")

--------------------------------
io.write("testing source.string and pump.all: ")
local source = ltn12.source.string(s)
sink, t = ltn12.sink.table()
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == s, "mismatch")
print("ok")

--------------------------------
io.write("testing source.table: ")
local inp = {'a','b','c','d','e'}
local source = ltn12.source.table(inp)
sink, t = ltn12.sink.table()
assert(ltn12.pump.all(source, sink), "returned error")
for i = 1, #inp do assert(t[i] == inp[i], "mismatch") end
print("ok")

--------------------------------
io.write("testing source.chain (with split): ")
source = ltn12.source.string(s)
filter = split(5)
source = ltn12.source.chain(source, filter)
sink, t = ltn12.sink.table()
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == s, "mismatch")
assert(filter(nil, 1), "filter not empty")
print("ok")

--------------------------------
io.write("testing source.chain (with several filters): ")
local function double(x) -- filter turning "ABC" into "AABBCC"
    if not x then return end
    local b={}
    for k in x:gmatch'.' do table.insert(b, k..k) end
    return table.concat(b)
end
source = ltn12.source.string(s)
source = ltn12.source.chain(source, double, double, double)
sink, t = ltn12.sink.table()
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == double(double(double(s))), "mismatch")
print("ok")

--------------------------------
io.write("testing source.chain (with split) and sink.chain (with merge): ")
source = ltn12.source.string(s)
filter = split(5)
source = ltn12.source.chain(source, filter)
local filter2 = merge(13)
sink, t = ltn12.sink.table()
sink = ltn12.sink.chain(filter2, sink)
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == s, "mismatch")
assert(filter(nil, 1), "filter not empty")
assert(filter2(nil, 1), "filter2 not empty")
print("ok")

--------------------------------
io.write("testing sink.chain (with several filters): ")
source = ltn12.source.string(s)
sink, t = ltn12.sink.table()
sink = ltn12.sink.chain(double, double, double, sink)
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == double(double(double(s))), "mismatch")
print("ok")

--------------------------------
io.write("testing filter.chain (and sink.chain, with split, merge): ")
source = ltn12.source.string(s)
filter = split(5)
filter2 = merge(13)
local chain = ltn12.filter.chain(filter, filter2)
sink, t = ltn12.sink.table()
sink = ltn12.sink.chain(chain, sink)
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == s, "mismatch")
assert(filter(nil, 1), "filter not empty")
assert(filter2(nil, 1), "filter2 not empty")
print("ok")

--------------------------------
io.write("testing filter.chain (and sink.chain, a bunch): ")
source = ltn12.source.string(s)
filter = split(5)
filter2 = merge(13)
local filter3 = split(7)
local filter4 = merge(11)
local filter5 = split(10)
chain = ltn12.filter.chain(filter, filter2, filter3, filter4, filter5)
sink, t = ltn12.sink.table()
sink = ltn12.sink.chain(chain, sink)
assert(ltn12.pump.all(source, sink))
assert(table.concat(t) == s, "mismatch")
assert(filter(nil, 1), "filter not empty")
assert(filter2(nil, 1), "filter2 not empty")
assert(filter3(nil, 1), "filter3 not empty")
assert(filter4(nil, 1), "filter4 not empty")
assert(filter5(nil, 1), "filter5 not empty")
print("ok")

--------------------------------
io.write("testing filter.chain (and source.chain, with split, merge): ")
source = ltn12.source.string(s)
filter = split(5)
filter2 = merge(13)
local chain = ltn12.filter.chain(filter, filter2)
sink, t = ltn12.sink.table()
source = ltn12.source.chain(source, chain)
assert(ltn12.pump.all(source, sink), "returned error")
assert(table.concat(t) == s, "mismatch")
assert(filter(nil, 1), "filter not empty")
assert(filter2(nil, 1), "filter2 not empty")
print("ok")

--------------------------------
io.write("testing filter.chain (and source.chain, a bunch): ")
source = ltn12.source.string(s)
filter = split(5)
filter2 = merge(13)
local filter3 = split(7)
local filter4 = merge(11)
local filter5 = split(10)
chain = ltn12.filter.chain(filter, filter2, filter3, filter4, filter5)
sink, t = ltn12.sink.table()
source = ltn12.source.chain(source, chain)
assert(ltn12.pump.all(source, sink))
assert(table.concat(t) == s, "mismatch")
assert(filter(nil, 1), "filter not empty")
assert(filter2(nil, 1), "filter2 not empty")
assert(filter3(nil, 1), "filter3 not empty")
assert(filter4(nil, 1), "filter4 not empty")
assert(filter5(nil, 1), "filter5 not empty")
print("ok")

