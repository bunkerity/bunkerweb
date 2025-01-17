-----------------------------------------------------------------------------
-- Little program to convert to and from Quoted-Printable
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local ltn12 = require("ltn12")
local mime = require("mime")
local convert
arg = arg or {}
local mode = arg and arg[1] or "-et"
if mode == "-et" then
    local normalize = mime.normalize()
    local qp = mime.encode("quoted-printable")
    local wrap = mime.wrap("quoted-printable")
    convert = ltn12.filter.chain(normalize, qp, wrap)
elseif mode == "-eb" then
    local qp = mime.encode("quoted-printable", "binary")
    local wrap = mime.wrap("quoted-printable")
    convert = ltn12.filter.chain(qp, wrap)
else convert = mime.decode("quoted-printable") end
local source = ltn12.source.chain(ltn12.source.file(io.stdin), convert)
local sink = ltn12.sink.file(io.stdout)
ltn12.pump.all(source, sink)
