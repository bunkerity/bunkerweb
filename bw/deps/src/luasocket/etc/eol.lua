-----------------------------------------------------------------------------
-- Little program to adjust end of line markers.
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local mime = require("mime")
local ltn12 = require("ltn12")
local marker = '\n'
if arg and arg[1] == '-d' then marker = '\r\n' end
local filter = mime.normalize(marker)
local source = ltn12.source.chain(ltn12.source.file(io.stdin), filter)
local sink = ltn12.sink.file(io.stdout)
ltn12.pump.all(source, sink)
